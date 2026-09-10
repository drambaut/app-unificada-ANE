"""Repositorio en memoria para ejecuciones de analisis transversal."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from app.analysis_runs.errors import (
    AnalysisRunNotFoundError,
    AnalysisStageNotFoundError,
    ConcurrentAnalysisRunError,
    IncompleteAnalysisPublicationError,
    InvalidAnalysisRetryError,
    InvalidAnalysisTransitionError,
)
from app.analysis_runs.models import (
    DEFAULT_STAGE_PROMPTS,
    STAGE_ORDER,
    AnalysisRun,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageRun,
)


class InMemoryAnalysisRunRepository:
    """Implementacion no persistente, util para pruebas y orquestacion local."""

    _ACTIVE_RUN_STATUSES = {AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING}

    def __init__(
        self,
        *,
        uuid_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uuid_factory = uuid_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runs: dict[str, AnalysisRun] = {}
        self._stage_ids_by_run: dict[str, list[str]] = {}
        self._stages: dict[str, AnalysisStageRun] = {}
        self._stage_by_run_and_type: dict[tuple[str, AnalysisStage], str] = {}
        self._latest_published_run_id: str | None = None

    def create_run(self, corpus_snapshot_id: str) -> AnalysisRun:
        for run in self._runs.values():
            if (
                run.corpus_snapshot_id == corpus_snapshot_id
                and run.status in self._ACTIVE_RUN_STATUSES
            ):
                raise ConcurrentAnalysisRunError(
                    f"Ya existe una ejecucion activa para el snapshot {corpus_snapshot_id}."
                )

        now = self._clock()
        run = AnalysisRun(
            id=self._uuid_factory(),
            corpus_snapshot_id=corpus_snapshot_id,
            status=AnalysisRunStatus.QUEUED,
            attempts=0,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            published_at=None,
            failed_at=None,
            error_message=None,
        )

        stages: list[AnalysisStageRun] = []
        for stage in STAGE_ORDER:
            spec = DEFAULT_STAGE_PROMPTS[stage]
            stages.append(
                AnalysisStageRun(
                    id=self._uuid_factory(),
                    analysis_run_id=run.id,
                    stage=stage,
                    status=AnalysisRunStatus.QUEUED,
                    prompt_id=spec.prompt_id,
                    prompt_version=spec.prompt_version,
                    contract_name=spec.contract_name,
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                    started_at=None,
                    completed_at=None,
                    failed_at=None,
                    error_message=None,
                    result_payload=None,
                )
            )

        self._runs[run.id] = run
        self._stage_ids_by_run[run.id] = [stage.id for stage in stages]
        for stage in stages:
            self._stages[stage.id] = stage
            self._stage_by_run_and_type[(run.id, stage.stage)] = stage.id
        return run

    def get_run(self, run_id: str) -> AnalysisRun | None:
        return self._runs.get(run_id)

    def get_active_run_for_snapshot(self, corpus_snapshot_id: str) -> AnalysisRun | None:
        active = [
            run
            for run in self._runs.values()
            if run.corpus_snapshot_id == corpus_snapshot_id
            and run.status in self._ACTIVE_RUN_STATUSES
        ]
        return max(active, key=lambda run: run.created_at) if active else None

    def get_latest_active_run(self) -> AnalysisRun | None:
        active = [
            run
            for run in self._runs.values()
            if run.status in self._ACTIVE_RUN_STATUSES
        ]
        return max(active, key=lambda run: run.created_at) if active else None

    def list_stages(self, run_id: str) -> list[AnalysisStageRun]:
        self._require_run(run_id)
        return [
            self._stages[stage_id]
            for stage_id in self._stage_ids_by_run.get(run_id, [])
        ]

    def get_stage(
        self, run_id: str, stage: AnalysisStage
    ) -> AnalysisStageRun | None:
        if run_id not in self._runs:
            return None
        stage_id = self._stage_by_run_and_type.get((run_id, stage))
        return self._stages.get(stage_id) if stage_id is not None else None

    def update_run_status(
        self,
        run_id: str,
        status: AnalysisRunStatus,
        *,
        error_message: str | None = None,
    ) -> AnalysisRun:
        run = self._require_run(run_id)
        self._validate_run_transition(run, status)
        if status == AnalysisRunStatus.COMPLETED:
            self._ensure_all_stages_completed(run_id)

        updated = self._build_run_transition(run, status, error_message)
        self._runs[run_id] = updated
        return updated

    def update_stage_status(
        self,
        run_id: str,
        stage: AnalysisStage,
        status: AnalysisRunStatus,
        *,
        error_message: str | None = None,
    ) -> AnalysisStageRun:
        self._require_run(run_id)
        current = self._require_stage(run_id, stage)
        self._validate_stage_transition(current, status)

        updated = self._build_stage_transition(current, status, error_message)
        self._stages[current.id] = updated
        return updated

    def save_stage_result(
        self, run_id: str, stage: AnalysisStage, result_payload: dict
    ) -> AnalysisStageRun:
        self._require_run(run_id)
        current = self._require_stage(run_id, stage)
        if current.status not in {
            AnalysisRunStatus.RUNNING,
            AnalysisRunStatus.COMPLETED,
        }:
            raise InvalidAnalysisTransitionError(
                f"No se puede guardar resultado para {stage.value} en estado {current.status.value}."
            )
        updated = replace(
            current,
            result_payload=copy.deepcopy(result_payload),
            updated_at=self._clock(),
        )
        self._stages[current.id] = updated
        return updated

    def get_latest_published_run(self) -> AnalysisRun | None:
        if self._latest_published_run_id is None:
            return None
        return self._runs.get(self._latest_published_run_id)

    def publish_run(self, run_id: str) -> AnalysisRun:
        run = self._require_run(run_id)
        if run.status != AnalysisRunStatus.COMPLETED:
            raise IncompleteAnalysisPublicationError(
                f"La ejecucion {run_id} debe estar completed antes de publicarse."
            )
        self._ensure_all_stages_completed(run_id)

        now = self._clock()
        published = replace(
            run,
            status=AnalysisRunStatus.PUBLISHED,
            published_at=now,
            updated_at=now,
            error_message=None,
        )
        self._runs[run_id] = published
        self._latest_published_run_id = run_id
        return published

    def prepare_stage_retry(
        self, run_id: str, stage: AnalysisStage
    ) -> list[AnalysisStageRun]:
        self._require_run(run_id)
        target = self._require_stage(run_id, stage)
        if target.status != AnalysisRunStatus.FAILED:
            raise InvalidAnalysisRetryError(
                f"La etapa {stage.value} debe estar failed para reintentarse."
            )

        now = self._clock()
        stages = self.list_stages(run_id)
        target_index = STAGE_ORDER.index(stage)
        updated_stages: list[AnalysisStageRun] = []
        for stage_run in stages:
            if STAGE_ORDER.index(stage_run.stage) >= target_index:
                updated_stages.append(
                    replace(
                        stage_run,
                        status=AnalysisRunStatus.QUEUED,
                        updated_at=now,
                        started_at=None,
                        completed_at=None,
                        failed_at=None,
                        error_message=None,
                        result_payload=None,
                    )
                )
            else:
                updated_stages.append(stage_run)

        for updated in updated_stages:
            self._stages[updated.id] = updated
        return updated_stages

    def fail_incomplete_run_for_retry(
        self, run_id: str, *, error_message: str
    ) -> AnalysisRun:
        run = self._require_run(run_id)
        if run.status not in self._ACTIVE_RUN_STATUSES:
            return run

        stages = self.list_stages(run_id)
        failed_stage = next(
            (stage for stage in stages if stage.status == AnalysisRunStatus.FAILED),
            None,
        )
        target = failed_stage or next(
            (
                stage
                for stage in stages
                if stage.status
                in {AnalysisRunStatus.RUNNING, AnalysisRunStatus.QUEUED}
            ),
            None,
        )
        if target is not None and target.status != AnalysisRunStatus.FAILED:
            self._stages[target.id] = replace(
                target,
                status=AnalysisRunStatus.FAILED,
                updated_at=self._clock(),
                failed_at=self._clock(),
                error_message=error_message,
            )
        failed_run = replace(
            run,
            status=AnalysisRunStatus.FAILED,
            updated_at=self._clock(),
            failed_at=self._clock(),
            error_message=error_message,
        )
        self._runs[run.id] = failed_run
        return failed_run

    def _require_run(self, run_id: str) -> AnalysisRun:
        run = self._runs.get(run_id)
        if run is None:
            raise AnalysisRunNotFoundError(f"No existe la ejecucion {run_id}.")
        return run

    def _require_stage(self, run_id: str, stage: AnalysisStage) -> AnalysisStageRun:
        stage_run = self.get_stage(run_id, stage)
        if stage_run is None:
            raise AnalysisStageNotFoundError(
                f"No existe la etapa {stage.value} para la ejecucion {run_id}."
            )
        return stage_run

    def _ensure_all_stages_completed(self, run_id: str) -> None:
        incomplete = [
            stage.stage.value
            for stage in self.list_stages(run_id)
            if stage.status != AnalysisRunStatus.COMPLETED
        ]
        if incomplete:
            raise IncompleteAnalysisPublicationError(
                f"La ejecucion {run_id} tiene etapas incompletas: {', '.join(incomplete)}."
            )

    def _validate_run_transition(
        self, run: AnalysisRun, target: AnalysisRunStatus
    ) -> None:
        valid = {
            AnalysisRunStatus.QUEUED: {AnalysisRunStatus.RUNNING},
            AnalysisRunStatus.RUNNING: {
                AnalysisRunStatus.COMPLETED,
                AnalysisRunStatus.FAILED,
            },
            AnalysisRunStatus.FAILED: {AnalysisRunStatus.RUNNING},
            AnalysisRunStatus.COMPLETED: set(),
            AnalysisRunStatus.PUBLISHED: set(),
        }
        if target not in valid[run.status]:
            raise InvalidAnalysisTransitionError(
                f"Transicion invalida para ejecucion {run.id}: {run.status.value} -> {target.value}."
            )

    def _validate_stage_transition(
        self, stage_run: AnalysisStageRun, target: AnalysisRunStatus
    ) -> None:
        valid = {
            AnalysisRunStatus.QUEUED: {AnalysisRunStatus.RUNNING},
            AnalysisRunStatus.RUNNING: {
                AnalysisRunStatus.COMPLETED,
                AnalysisRunStatus.FAILED,
            },
            AnalysisRunStatus.FAILED: set(),
            AnalysisRunStatus.COMPLETED: set(),
            AnalysisRunStatus.PUBLISHED: set(),
        }
        if target not in valid[stage_run.status]:
            raise InvalidAnalysisTransitionError(
                "Transicion invalida para etapa "
                f"{stage_run.stage.value}: {stage_run.status.value} -> {target.value}."
            )

    def _build_run_transition(
        self,
        run: AnalysisRun,
        target: AnalysisRunStatus,
        error_message: str | None,
    ) -> AnalysisRun:
        now = self._clock()
        if target == AnalysisRunStatus.RUNNING:
            return replace(
                run,
                status=target,
                attempts=run.attempts + 1,
                updated_at=now,
                started_at=now,
                completed_at=None,
                failed_at=None,
                error_message=None,
            )
        if target == AnalysisRunStatus.COMPLETED:
            return replace(
                run,
                status=target,
                updated_at=now,
                completed_at=now,
                failed_at=None,
                error_message=None,
            )
        if target == AnalysisRunStatus.FAILED:
            return replace(
                run,
                status=target,
                updated_at=now,
                failed_at=now,
                error_message=error_message,
            )
        raise InvalidAnalysisTransitionError(
            f"No se puede actualizar ejecucion {run.id} a {target.value}."
        )

    def _build_stage_transition(
        self,
        stage_run: AnalysisStageRun,
        target: AnalysisRunStatus,
        error_message: str | None,
    ) -> AnalysisStageRun:
        now = self._clock()
        if target == AnalysisRunStatus.RUNNING:
            return replace(
                stage_run,
                status=target,
                attempts=stage_run.attempts + 1,
                updated_at=now,
                started_at=now,
                completed_at=None,
                failed_at=None,
                error_message=None,
            )
        if target == AnalysisRunStatus.COMPLETED:
            return replace(
                stage_run,
                status=target,
                updated_at=now,
                completed_at=now,
                failed_at=None,
                error_message=None,
            )
        if target == AnalysisRunStatus.FAILED:
            return replace(
                stage_run,
                status=target,
                updated_at=now,
                failed_at=now,
                error_message=error_message,
            )
        raise InvalidAnalysisTransitionError(
            f"No se puede actualizar etapa {stage_run.stage.value} a {target.value}."
        )
