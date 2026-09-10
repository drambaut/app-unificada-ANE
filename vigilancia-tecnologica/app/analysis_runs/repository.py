"""Contrato de persistencia para ejecuciones de analisis transversal."""

from __future__ import annotations

from typing import Protocol

from app.analysis_runs.models import AnalysisRun, AnalysisRunStatus, AnalysisStage, AnalysisStageRun


class AnalysisRunRepository(Protocol):
    """Repositorio abstracto, sin referencias a Supabase."""

    def create_run(self, corpus_snapshot_id: str) -> AnalysisRun:
        """Crea una ejecucion con sus tres etapas versionadas."""

    def get_run(self, run_id: str) -> AnalysisRun | None:
        """Obtiene una ejecucion por ID."""

    def get_active_run_for_snapshot(self, corpus_snapshot_id: str) -> AnalysisRun | None:
        """Obtiene la ejecucion activa mas reciente para un snapshot."""

    def get_latest_active_run(self) -> AnalysisRun | None:
        """Obtiene la ejecucion activa mas reciente."""

    def list_stages(self, run_id: str) -> list[AnalysisStageRun]:
        """Lista las etapas de una ejecucion en orden canonico."""

    def get_stage(
        self, run_id: str, stage: AnalysisStage
    ) -> AnalysisStageRun | None:
        """Obtiene una etapa especifica."""

    def update_run_status(
        self,
        run_id: str,
        status: AnalysisRunStatus,
        *,
        error_message: str | None = None,
    ) -> AnalysisRun:
        """Actualiza el estado de una ejecucion."""

    def update_stage_status(
        self,
        run_id: str,
        stage: AnalysisStage,
        status: AnalysisRunStatus,
        *,
        error_message: str | None = None,
    ) -> AnalysisStageRun:
        """Actualiza el estado de una etapa."""

    def save_stage_result(
        self, run_id: str, stage: AnalysisStage, result_payload: dict
    ) -> AnalysisStageRun:
        """Guarda el resultado estructurado de una etapa."""

    def get_latest_published_run(self) -> AnalysisRun | None:
        """Obtiene la ejecucion publicada vigente."""

    def publish_run(self, run_id: str) -> AnalysisRun:
        """Publica atomica y exclusivamente una ejecucion completa."""

    def prepare_stage_retry(
        self, run_id: str, stage: AnalysisStage
    ) -> list[AnalysisStageRun]:
        """Prepara el reintento explicito de una etapa fallida."""

    def fail_incomplete_run_for_retry(
        self, run_id: str, *, error_message: str
    ) -> AnalysisRun:
        """Marca una ejecucion incompleta como failed para habilitar retry."""

