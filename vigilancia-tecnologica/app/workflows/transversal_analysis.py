"""Workflow integral para analisis transversal del corpus."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from app.analysis_runs.models import (
    STAGE_ORDER,
    AnalysisRun,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageRun,
)
from app.analysis_runs.repository import AnalysisRunRepository
from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.context_builder import CorpusContextBuilder
from app.corpus_snapshots.models import CorpusSnapshot, FrozenDict, PromptContext
from app.documents.models import Document
from app.llm.base import LLMInput
from app.llm.errors import InvalidLLMJSONError
from app.llm.service import ExtractionResult, StructuredExtractionService
from app.results.models import PersistenceBundle
from app.scoring.strategic import score_strategic_assessment


@dataclass(frozen=True)
class TransversalAnalysisWorkflowResult:
    snapshot: CorpusSnapshot
    run: AnalysisRun
    stages: tuple[AnalysisStageRun, ...]
    results: dict[AnalysisStage, ExtractionResult]
    completed_at: datetime | None


class TransversalAnalysisWorkflowError(Exception):
    """Error de workflow sin incluir payloads completos."""

    def __init__(
        self,
        *,
        stage: AnalysisStage | str,
        run_id: str | None,
        snapshot_id: str | None,
        original_error: Exception,
    ) -> None:
        self.stage = stage.value if isinstance(stage, AnalysisStage) else stage
        self.run_id = run_id
        self.snapshot_id = snapshot_id
        self.original_error = original_error
        super().__init__(
            "Fallo en analisis transversal "
            f"stage={self.stage} run_id={run_id} snapshot_id={snapshot_id}: "
            f"{type(original_error).__name__}: {original_error}"
        )


class TransversalAnalysisWorkflow:
    """Coordina snapshot, contextos, LLM estructurado y publicacion."""

    def __init__(
        self,
        *,
        snapshot_builder: CorpusSnapshotBuilder,
        context_builder: CorpusContextBuilder,
        extraction_service: StructuredExtractionService,
        analysis_run_repository: AnalysisRunRepository,
        strategic_assessment_scorer: Callable[[dict[str, Any]], dict[str, Any]]
        | None = None,
        use_empty_strategic_assessment: bool = False,
    ) -> None:
        self._snapshot_builder = snapshot_builder
        self._context_builder = context_builder
        self._extraction_service = extraction_service
        self._analysis_runs = analysis_run_repository
        self._use_empty_strategic_assessment = use_empty_strategic_assessment
        self._strategic_assessment_scorer = (
            strategic_assessment_scorer or score_strategic_assessment
        )

    def run(
        self,
        *,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        snapshot: CorpusSnapshot | None = None,
        selection_criteria: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        auto_publish: bool = True,
    ) -> TransversalAnalysisWorkflowResult:
        created_snapshot: CorpusSnapshot | None = snapshot
        run: AnalysisRun | None = None
        try:
            if created_snapshot is None:
                created_snapshot = self._snapshot_builder.build_snapshot(
                    documents=documents,
                    bundles=bundles,
                    selection_criteria=selection_criteria,
                    metadata=metadata,
                )
            run = self._analysis_runs.create_run(created_snapshot.id)
            run = self._analysis_runs.update_run_status(
                run.id, AnalysisRunStatus.RUNNING
            )
            return self._execute_run(
                run=run,
                snapshot=created_snapshot,
                documents=documents,
                bundles=bundles,
                auto_publish=auto_publish,
                skip_completed=False,
            )
        except Exception as exc:
            if isinstance(exc, TransversalAnalysisWorkflowError):
                raise
            raise TransversalAnalysisWorkflowError(
                stage="setup",
                run_id=run.id if run else None,
                snapshot_id=created_snapshot.id if created_snapshot else None,
                original_error=exc,
            ) from exc

    def retry(
        self,
        *,
        run_id: str,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        auto_publish: bool = True,
    ) -> TransversalAnalysisWorkflowResult:
        run = self._analysis_runs.get_run(run_id)
        if run is None:
            raise TransversalAnalysisWorkflowError(
                stage="retry",
                run_id=run_id,
                snapshot_id=snapshot.id,
                original_error=ValueError(f"No existe la ejecucion {run_id}."),
            )
        if run.corpus_snapshot_id != snapshot.id:
            raise TransversalAnalysisWorkflowError(
                stage="retry",
                run_id=run_id,
                snapshot_id=snapshot.id,
                original_error=ValueError("El run no pertenece al snapshot indicado."),
            )

        failed_stages = [
            stage
            for stage in self._analysis_runs.list_stages(run.id)
            if stage.status == AnalysisRunStatus.FAILED
        ]
        if not failed_stages:
            raise TransversalAnalysisWorkflowError(
                stage="retry",
                run_id=run_id,
                snapshot_id=snapshot.id,
                original_error=ValueError("No hay etapa failed para reintentar."),
            )
        retry_stage = min(failed_stages, key=lambda item: STAGE_ORDER.index(item.stage))
        try:
            self._analysis_runs.prepare_stage_retry(run.id, retry_stage.stage)
            run = self._analysis_runs.update_run_status(
                run.id, AnalysisRunStatus.RUNNING
            )
            return self._execute_run(
                run=run,
                snapshot=snapshot,
                documents=documents,
                bundles=bundles,
                auto_publish=auto_publish,
                skip_completed=True,
            )
        except Exception as exc:
            if isinstance(exc, TransversalAnalysisWorkflowError):
                raise
            raise TransversalAnalysisWorkflowError(
                stage=retry_stage.stage,
                run_id=run.id,
                snapshot_id=snapshot.id,
                original_error=exc,
            ) from exc

    def _execute_run(
        self,
        *,
        run: AnalysisRun,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        auto_publish: bool,
        skip_completed: bool,
    ) -> TransversalAnalysisWorkflowResult:
        results = self._existing_results(run.id) if skip_completed else {}
        thematic_result = results.get(AnalysisStage.THEMATIC_LANDSCAPE)

        for stage_run in self._analysis_runs.list_stages(run.id):
            if skip_completed and stage_run.status == AnalysisRunStatus.COMPLETED:
                continue
            try:
                stage_run = self._analysis_runs.update_stage_status(
                    run.id, stage_run.stage, AnalysisRunStatus.RUNNING
                )
                context = self._build_context(
                    stage_run=stage_run,
                    snapshot=snapshot,
                    documents=documents,
                    bundles=bundles,
                    thematic_result=thematic_result.payload
                    if thematic_result is not None
                    else None,
                )
                extraction_result = self._extract(stage_run, context)
                self._analysis_runs.save_stage_result(
                    run.id, stage_run.stage, extraction_result.payload
                )
                self._analysis_runs.update_stage_status(
                    run.id, stage_run.stage, AnalysisRunStatus.COMPLETED
                )
                results[stage_run.stage] = extraction_result
                if stage_run.stage == AnalysisStage.THEMATIC_LANDSCAPE:
                    thematic_result = extraction_result
            except Exception as exc:
                self._fail_stage_and_run(run.id, stage_run.stage, exc)
                raise TransversalAnalysisWorkflowError(
                    stage=stage_run.stage,
                    run_id=run.id,
                    snapshot_id=snapshot.id,
                    original_error=exc,
                ) from exc

        run = self._analysis_runs.update_run_status(
            run.id, AnalysisRunStatus.COMPLETED
        )
        if auto_publish:
            run = self._analysis_runs.publish_run(run.id)
        return TransversalAnalysisWorkflowResult(
            snapshot=snapshot,
            run=run,
            stages=tuple(self._analysis_runs.list_stages(run.id)),
            results=results,
            completed_at=run.completed_at,
        )

    def _build_context(
        self,
        *,
        stage_run: AnalysisStageRun,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        thematic_result: dict | None,
    ) -> PromptContext:
        if stage_run.stage == AnalysisStage.THEMATIC_LANDSCAPE:
            return self._context_builder.build_thematic_landscape_context(
                snapshot=snapshot,
                documents=documents,
                bundles=bundles,
                prompt_id=stage_run.prompt_id,
                prompt_version=stage_run.prompt_version,
            )
        if stage_run.stage == AnalysisStage.REGULATORY_INTELLIGENCE:
            return self._context_builder.build_regulatory_intelligence_context(
                snapshot=snapshot,
                documents=documents,
                bundles=bundles,
                thematic_result=thematic_result,
                prompt_id=stage_run.prompt_id,
                prompt_version=stage_run.prompt_version,
            )
        if stage_run.stage == AnalysisStage.STRATEGIC_ASSESSMENT:
            return self._context_builder.build_strategic_assessment_context(
                snapshot=snapshot,
                documents=documents,
                bundles=bundles,
                thematic_result=thematic_result,
                prompt_id=stage_run.prompt_id,
                prompt_version=stage_run.prompt_version,
            )
        raise ValueError(f"Etapa no soportada: {stage_run.stage}.")

    def _extract(
        self, stage_run: AnalysisStageRun, context: PromptContext
    ) -> ExtractionResult:
        text = self._canonical_json(context.payload)
        input_data = LLMInput(
            text=text,
            metadata={
                "snapshot_id": context.snapshot_id,
                "context_hash": context.context_hash,
                "stage": stage_run.stage.value,
            },
        )
        if (
            stage_run.stage == AnalysisStage.STRATEGIC_ASSESSMENT
            and self._use_empty_strategic_assessment
        ):
            return self._empty_strategic_assessment(stage_run)
        try:
            result = self._extraction_service.extract(
                prompt_id=stage_run.prompt_id,
                version=stage_run.prompt_version,
                input_data=input_data,
            )
        except InvalidLLMJSONError:
            if stage_run.stage != AnalysisStage.STRATEGIC_ASSESSMENT:
                raise
            result = self._empty_strategic_assessment(stage_run)
        if result.contract_name != stage_run.contract_name:
            raise ValueError(
                f"Contrato inesperado para {stage_run.stage.value}: "
                f"{result.contract_name} != {stage_run.contract_name}."
            )
        if stage_run.stage == AnalysisStage.STRATEGIC_ASSESSMENT:
            scored_payload = self._strategic_assessment_scorer(result.payload)
            return ExtractionResult(
                payload=scored_payload,
                prompt_id=result.prompt_id,
                prompt_version=result.prompt_version,
                contract_name=result.contract_name,
                model_name=result.model_name,
            )
        return result

    def _empty_strategic_assessment(
        self, stage_run: AnalysisStageRun
    ) -> ExtractionResult:
        return ExtractionResult(
            payload={
                "importance_assessments": [],
                "opportunity_assessments": [],
                "alignment_assessments": [],
            },
            prompt_id=stage_run.prompt_id,
            prompt_version=stage_run.prompt_version,
            contract_name=stage_run.contract_name,
            model_name="fallback-empty-strategic-assessment",
        )

    def _existing_results(self, run_id: str) -> dict[AnalysisStage, ExtractionResult]:
        results: dict[AnalysisStage, ExtractionResult] = {}
        for stage in self._analysis_runs.list_stages(run_id):
            if (
                stage.status == AnalysisRunStatus.COMPLETED
                and stage.result_payload is not None
            ):
                results[stage.stage] = ExtractionResult(
                    payload=stage.result_payload,
                    prompt_id=stage.prompt_id,
                    prompt_version=stage.prompt_version,
                    contract_name=stage.contract_name,
                    model_name="previous-stage-result",
                )
        return results

    def _fail_stage_and_run(
        self, run_id: str, stage: AnalysisStage, exc: Exception
    ) -> None:
        message = f"{type(exc).__name__}: {exc}"
        try:
            self._analysis_runs.update_stage_status(
                run_id, stage, AnalysisRunStatus.FAILED, error_message=message
            )
        finally:
            self._analysis_runs.update_run_status(
                run_id, AnalysisRunStatus.FAILED, error_message=message
            )

    def _canonical_json(self, payload: Mapping[str, Any]) -> str:
        return json.dumps(
            self._plain(payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _plain(self, value: Any):
        if isinstance(value, FrozenDict):
            return {key: self._plain(child) for key, child in value.items()}
        if isinstance(value, Mapping):
            return {key: self._plain(child) for key, child in value.items()}
        if isinstance(value, tuple | list):
            return [self._plain(child) for child in value]
        return value
