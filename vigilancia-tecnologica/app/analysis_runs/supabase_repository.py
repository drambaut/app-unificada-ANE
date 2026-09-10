"""Repositorio Supabase para ejecuciones de analisis transversal."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Callable
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
from app.core.settings import Settings, load_settings
from app.storage.errors import StorageConfigurationError


class SupabaseAnalysisRunRepository:
    """Implementacion Supabase del contrato `AnalysisRunRepository`."""

    _ACTIVE_RUN_STATUSES = {AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING}

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        uuid_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client
        self._client_factory = client_factory
        self._uuid_factory = uuid_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_run(self, corpus_snapshot_id: str) -> AnalysisRun:
        rows = (
            self._table("analysis_runs")
            .select("*")
            .eq("corpus_snapshot_id", corpus_snapshot_id)
            .execute()
            .data
            or []
        )
        for row in rows:
            if AnalysisRunStatus(row["status"]) in self._ACTIVE_RUN_STATUSES:
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
        saved = _run_from_row(self._insert("analysis_runs", _run_to_row(run)))
        for stage in STAGE_ORDER:
            spec = DEFAULT_STAGE_PROMPTS[stage]
            stage_run = AnalysisStageRun(
                id=self._uuid_factory(),
                analysis_run_id=saved.id,
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
            self._insert("analysis_stage_runs", _stage_to_row(stage_run))
        return saved

    def get_run(self, run_id: str) -> AnalysisRun | None:
        row = _single(
            self._table("analysis_runs")
            .select("*")
            .eq("id", run_id)
            .limit(1)
            .execute()
            .data
        )
        return _run_from_row(row) if row is not None else None

    def get_active_run_for_snapshot(self, corpus_snapshot_id: str) -> AnalysisRun | None:
        rows = (
            self._table("analysis_runs")
            .select("*")
            .eq("corpus_snapshot_id", corpus_snapshot_id)
            .execute()
            .data
            or []
        )
        return _latest_active_run(rows, self._ACTIVE_RUN_STATUSES)

    def get_latest_active_run(self) -> AnalysisRun | None:
        rows = self._table("analysis_runs").select("*").execute().data or []
        return _latest_active_run(rows, self._ACTIVE_RUN_STATUSES)

    def list_stages(self, run_id: str) -> list[AnalysisStageRun]:
        self._require_run(run_id)
        rows = (
            self._table("analysis_stage_runs")
            .select("*")
            .eq("analysis_run_id", run_id)
            .execute()
            .data
            or []
        )
        stages = [_stage_from_row(row) for row in rows]
        return sorted(stages, key=lambda stage_run: STAGE_ORDER.index(stage_run.stage))

    def get_stage(
        self, run_id: str, stage: AnalysisStage
    ) -> AnalysisStageRun | None:
        if self.get_run(run_id) is None:
            return None
        row = _single(
            self._table("analysis_stage_runs")
            .select("*")
            .eq("analysis_run_id", run_id)
            .eq("stage", stage.value)
            .limit(1)
            .execute()
            .data
        )
        return _stage_from_row(row) if row is not None else None

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
        row = _single(
            self._table("analysis_runs")
            .update(self._run_transition_payload(run, status, error_message))
            .eq("id", run_id)
            .execute()
            .data
        )
        if row is None:
            raise AnalysisRunNotFoundError(f"No existe la ejecucion {run_id}.")
        return _run_from_row(row)

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
        row = _single(
            self._table("analysis_stage_runs")
            .update(self._stage_transition_payload(current, status, error_message))
            .eq("id", current.id)
            .execute()
            .data
        )
        if row is None:
            raise AnalysisStageNotFoundError(
                f"No existe la etapa {stage.value} para la ejecucion {run_id}."
            )
        return _stage_from_row(row)

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
        row = _single(
            self._table("analysis_stage_runs")
            .update(
                {
                    "result_payload": copy.deepcopy(result_payload),
                    "updated_at": self._clock().isoformat(),
                }
            )
            .eq("id", current.id)
            .execute()
            .data
        )
        return _stage_from_row(row)

    def get_latest_published_run(self) -> AnalysisRun | None:
        publication = _single(
            self._table("dashboard_publications")
            .select("*")
            .eq("is_current", True)
            .limit(1)
            .execute()
            .data
        )
        if publication is None:
            return None
        return self.get_run(publication["analysis_run_id"])

    def publish_run(self, run_id: str) -> AnalysisRun:
        run = self._require_run(run_id)
        if run.status != AnalysisRunStatus.COMPLETED:
            raise IncompleteAnalysisPublicationError(
                f"La ejecucion {run_id} debe estar completed antes de publicarse."
            )
        self._ensure_all_stages_completed(run_id)
        self._client_instance().rpc(
            "publish_analysis_run", {"target_analysis_run_id": run_id}
        ).execute()
        published = self.get_run(run_id)
        if published is None:
            raise AnalysisRunNotFoundError(f"No existe la ejecucion {run_id}.")
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
        target_index = STAGE_ORDER.index(stage)
        updated: list[AnalysisStageRun] = []
        now = self._clock()
        for stage_run in self.list_stages(run_id):
            if STAGE_ORDER.index(stage_run.stage) >= target_index:
                row = _single(
                    self._table("analysis_stage_runs")
                    .update(
                        {
                            "status": AnalysisRunStatus.QUEUED.value,
                            "updated_at": now.isoformat(),
                            "started_at": None,
                            "completed_at": None,
                            "failed_at": None,
                            "error_message": None,
                            "result_payload": None,
                        }
                    )
                    .eq("id", stage_run.id)
                    .execute()
                    .data
                )
                updated.append(_stage_from_row(row))
            else:
                updated.append(stage_run)
        return updated

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
        now = self._clock().isoformat()
        if target is not None and target.status != AnalysisRunStatus.FAILED:
            self._table("analysis_stage_runs").update(
                {
                    "status": AnalysisRunStatus.FAILED.value,
                    "updated_at": now,
                    "failed_at": now,
                    "error_message": error_message,
                }
            ).eq("id", target.id).execute()

        row = _single(
            self._table("analysis_runs")
            .update(
                {
                    "status": AnalysisRunStatus.FAILED.value,
                    "updated_at": now,
                    "failed_at": now,
                    "error_message": error_message,
                }
            )
            .eq("id", run_id)
            .execute()
            .data
        )
        if row is None:
            raise AnalysisRunNotFoundError(f"No existe la ejecucion {run_id}.")
        return _run_from_row(row)

    def _require_run(self, run_id: str) -> AnalysisRun:
        run = self.get_run(run_id)
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

    def _run_transition_payload(
        self,
        run: AnalysisRun,
        target: AnalysisRunStatus,
        error_message: str | None,
    ) -> dict[str, Any]:
        now = self._clock().isoformat()
        if target == AnalysisRunStatus.RUNNING:
            return {
                "status": target.value,
                "attempts": run.attempts + 1,
                "updated_at": now,
                "started_at": now,
                "completed_at": None,
                "failed_at": None,
                "error_message": None,
            }
        if target == AnalysisRunStatus.COMPLETED:
            return {
                "status": target.value,
                "updated_at": now,
                "completed_at": now,
                "failed_at": None,
                "error_message": None,
            }
        if target == AnalysisRunStatus.FAILED:
            return {
                "status": target.value,
                "updated_at": now,
                "failed_at": now,
                "error_message": error_message,
            }
        raise InvalidAnalysisTransitionError(
            f"No se puede actualizar ejecucion {run.id} a {target.value}."
        )

    def _stage_transition_payload(
        self,
        stage_run: AnalysisStageRun,
        target: AnalysisRunStatus,
        error_message: str | None,
    ) -> dict[str, Any]:
        now = self._clock().isoformat()
        if target == AnalysisRunStatus.RUNNING:
            return {
                "status": target.value,
                "attempts": stage_run.attempts + 1,
                "updated_at": now,
                "started_at": now,
                "completed_at": None,
                "failed_at": None,
                "error_message": None,
            }
        if target == AnalysisRunStatus.COMPLETED:
            return {
                "status": target.value,
                "updated_at": now,
                "completed_at": now,
                "failed_at": None,
                "error_message": None,
            }
        if target == AnalysisRunStatus.FAILED:
            return {
                "status": target.value,
                "updated_at": now,
                "failed_at": now,
                "error_message": error_message,
            }
        raise InvalidAnalysisTransitionError(
            f"No se puede actualizar etapa {stage_run.stage.value} a {target.value}."
        )

    def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._table(table).insert(payload).execute().data
        return rows[0]

    def _table(self, name: str):
        return self._client_instance().table(name)

    def _client_instance(self):
        if self._client is not None:
            return self._client
        key = self._settings.supabase_backend_key
        if not self._settings.supabase_url or not key:
            raise StorageConfigurationError(
                "SUPABASE_URL y SUPABASE_KEY son requeridos para Supabase."
            )
        factory = self._client_factory or self._default_client_factory
        self._client = factory(self._settings.supabase_url, key)
        return self._client

    def _default_client_factory(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError as exc:
            raise StorageConfigurationError(
                "Instale la dependencia 'supabase' para usar repositorios Supabase."
            ) from exc
        return create_client(url, key)


def _run_to_row(run: AnalysisRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "corpus_snapshot_id": run.corpus_snapshot_id,
        "status": run.status.value,
        "attempts": run.attempts,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "started_at": _dt(run.started_at),
        "completed_at": _dt(run.completed_at),
        "published_at": _dt(run.published_at),
        "failed_at": _dt(run.failed_at),
        "error_message": run.error_message,
    }


def _run_from_row(row: dict[str, Any]) -> AnalysisRun:
    return AnalysisRun(
        id=row["id"],
        corpus_snapshot_id=row["corpus_snapshot_id"],
        status=AnalysisRunStatus(row["status"]),
        attempts=row["attempts"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        started_at=_parse_datetime(row.get("started_at")),
        completed_at=_parse_datetime(row.get("completed_at")),
        published_at=_parse_datetime(row.get("published_at")),
        failed_at=_parse_datetime(row.get("failed_at")),
        error_message=row.get("error_message"),
    )


def _latest_active_run(
    rows: list[dict[str, Any]], active_statuses: set[AnalysisRunStatus]
) -> AnalysisRun | None:
    active_rows = [
        row
        for row in rows
        if AnalysisRunStatus(row["status"]) in active_statuses
    ]
    if not active_rows:
        return None
    latest = max(active_rows, key=lambda row: _parse_datetime(row["created_at"]))
    return _run_from_row(latest)


def _stage_to_row(stage_run: AnalysisStageRun) -> dict[str, Any]:
    return {
        "id": stage_run.id,
        "analysis_run_id": stage_run.analysis_run_id,
        "stage": stage_run.stage.value,
        "status": stage_run.status.value,
        "prompt_id": stage_run.prompt_id,
        "prompt_version": stage_run.prompt_version,
        "contract_name": stage_run.contract_name,
        "attempts": stage_run.attempts,
        "created_at": stage_run.created_at.isoformat(),
        "updated_at": stage_run.updated_at.isoformat(),
        "started_at": _dt(stage_run.started_at),
        "completed_at": _dt(stage_run.completed_at),
        "failed_at": _dt(stage_run.failed_at),
        "error_message": stage_run.error_message,
        "result_payload": stage_run.result_payload,
    }


def _stage_from_row(row: dict[str, Any]) -> AnalysisStageRun:
    return AnalysisStageRun(
        id=row["id"],
        analysis_run_id=row["analysis_run_id"],
        stage=AnalysisStage(row["stage"]),
        status=AnalysisRunStatus(row["status"]),
        prompt_id=row["prompt_id"],
        prompt_version=row["prompt_version"],
        contract_name=row["contract_name"],
        attempts=row["attempts"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        started_at=_parse_datetime(row.get("started_at")),
        completed_at=_parse_datetime(row.get("completed_at")),
        failed_at=_parse_datetime(row.get("failed_at")),
        error_message=row.get("error_message"),
        result_payload=row.get("result_payload"),
    )


def _single(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not rows:
        return None
    return rows[0]


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
