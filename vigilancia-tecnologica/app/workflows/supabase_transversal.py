"""Orquestacion transversal alimentada desde repositorios Supabase."""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis_runs.models import AnalysisRunStatus
from app.documents.models import Document
from app.results.models import PersistenceBundle
from app.workflows.transversal_analysis import (
    TransversalAnalysisWorkflow,
    TransversalAnalysisWorkflowResult,
)


class SupabaseTransversalAnalysisWorkflowError(Exception):
    """Fallo controlado antes de lanzar el analisis transversal."""


@dataclass(frozen=True)
class SupabaseCorpusData:
    documents: list[Document]
    bundles: list[PersistenceBundle]


class SupabaseTransversalAnalysisWorkflow:
    """Carga corpus `processed` desde Supabase y ejecuta el workflow transversal."""

    def __init__(
        self,
        *,
        document_repository,
        result_repository,
        snapshot_repository=None,
        analysis_run_repository=None,
        transversal_workflow: TransversalAnalysisWorkflow,
    ) -> None:
        self._document_repository = document_repository
        self._result_repository = result_repository
        self._snapshot_repository = snapshot_repository
        self._analysis_run_repository = analysis_run_repository
        self._transversal_workflow = transversal_workflow

    def load_processed_corpus(self) -> SupabaseCorpusData:
        documents = self._document_repository.list_processed_documents()
        if not documents:
            raise SupabaseTransversalAnalysisWorkflowError(
                "No hay documentos processed en Supabase para analisis transversal."
            )
        bundles: list[PersistenceBundle] = []
        missing_bundle_document_ids: list[str] = []
        for document in documents:
            bundle = self._result_repository.get_bundle(document.id)
            if bundle is None:
                missing_bundle_document_ids.append(document.id)
            else:
                bundles.append(bundle)
        if missing_bundle_document_ids:
            raise SupabaseTransversalAnalysisWorkflowError(
                "Documentos processed sin PersistenceBundle: "
                + ", ".join(sorted(missing_bundle_document_ids))
            )
        return SupabaseCorpusData(documents=documents, bundles=bundles)

    def run(
        self,
        *,
        selection_criteria: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        auto_publish: bool = True,
    ) -> TransversalAnalysisWorkflowResult:
        corpus = self.load_processed_corpus()
        criteria = {"status": "processed", **dict(selection_criteria or {})}
        return self._transversal_workflow.run(
            documents=corpus.documents,
            bundles=corpus.bundles,
            selection_criteria=criteria,
            metadata=metadata,
            auto_publish=auto_publish,
        )

    def retry_latest_active(
        self,
        *,
        auto_publish: bool = True,
    ) -> TransversalAnalysisWorkflowResult:
        if self._analysis_run_repository is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                "No hay repositorio de ejecuciones configurado para retry."
            )
        run = self._analysis_run_repository.get_latest_active_run()
        if run is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                "No hay ejecuciones activas para reintentar."
            )
        return self.retry_run(run.id, auto_publish=auto_publish)

    def retry_run(
        self,
        run_id: str,
        *,
        auto_publish: bool = True,
    ) -> TransversalAnalysisWorkflowResult:
        if self._snapshot_repository is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                "No hay repositorio de snapshots configurado para retry."
            )
        if self._analysis_run_repository is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                "No hay repositorio de ejecuciones configurado para retry."
            )
        run = self._analysis_run_repository.get_run(run_id)
        if run is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                f"No existe la ejecucion {run_id}."
            )
        snapshot = self._snapshot_repository.get_snapshot(run.corpus_snapshot_id)
        if snapshot is None:
            raise SupabaseTransversalAnalysisWorkflowError(
                f"No existe el snapshot {run.corpus_snapshot_id}."
            )
        if run.status in {AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING}:
            self._analysis_run_repository.fail_incomplete_run_for_retry(
                run.id,
                error_message=(
                    "Ejecucion activa recuperada para retry desde "
                    "run_supabase_transversal.py."
                ),
            )
        corpus = self.load_processed_corpus()
        return self._transversal_workflow.retry(
            run_id=run.id,
            snapshot=snapshot,
            documents=corpus.documents,
            bundles=corpus.bundles,
            auto_publish=auto_publish,
        )
