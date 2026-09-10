"""Pruebas del repositorio Supabase de ejecuciones transversales."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.analysis_runs.errors import (
    ConcurrentAnalysisRunError,
    IncompleteAnalysisPublicationError,
    InvalidAnalysisRetryError,
)
from app.analysis_runs.models import AnalysisRunStatus, AnalysisStage
from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository
from app.core.settings import load_settings
from app.storage.errors import StorageConfigurationError


NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table: "FakeTable", operation: str, payload=None) -> None:
        self.table = table
        self.operation = operation
        self.payload = payload
        self.filters: dict[str, Any] = {}
        self.limit_count: int | None = None
        self.order_column: str | None = None

    def select(self, _columns: str):
        return self

    def eq(self, column: str, value):
        self.filters[column] = value
        return self

    def limit(self, count: int):
        self.limit_count = count
        return self

    def order(self, column: str):
        self.order_column = column
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def execute(self):
        rows = self.table.rows
        if self.operation == "insert":
            stored = dict(self.payload)
            rows.append(stored)
            return FakeResponse([stored])
        selected = [
            row
            for row in rows
            if all(row.get(column) == value for column, value in self.filters.items())
        ]
        if self.operation == "update":
            for row in selected:
                row.update(self.payload)
            return FakeResponse(selected)
        if self.order_column is not None:
            selected.sort(key=lambda row: row[self.order_column])
        if self.limit_count is not None:
            selected = selected[: self.limit_count]
        return FakeResponse(selected)


class FakeTable:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def select(self, columns: str):
        return FakeQuery(self, "select").select(columns)

    def insert(self, payload):
        return FakeQuery(self, "insert", payload)

    def update(self, payload):
        return FakeQuery(self, "update", payload)


class FakeRpc:
    def __init__(self, client: "FakeClient", params: dict[str, Any]) -> None:
        self.client = client
        self.params = params

    def execute(self):
        run_id = self.params["target_analysis_run_id"]
        runs = self.client.table("analysis_runs").rows
        for row in runs:
            if row["id"] == run_id:
                row.update(
                    {
                        "status": "published",
                        "published_at": NOW.isoformat(),
                        "updated_at": NOW.isoformat(),
                        "error_message": None,
                    }
                )
                self.client.table("dashboard_publications").rows.clear()
                self.client.table("dashboard_publications").rows.append(
                    {
                        "id": "publication-1",
                        "analysis_run_id": run_id,
                        "snapshot_id": row["corpus_snapshot_id"],
                        "published_at": NOW.isoformat(),
                        "is_current": True,
                    }
                )
                return FakeResponse(["publication-1"])
        return FakeResponse([])


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str):
        return self.tables.setdefault(name, FakeTable())

    def rpc(self, name: str, params: dict[str, Any]):
        assert name == "publish_analysis_run"
        return FakeRpc(self, params)


def settings():
    return load_settings(
        environ={
            "DATA_DIR": "../data",
            "OUTPUT_DIR": "outputs",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "test-key",
        }
    )


def id_factory():
    ids = iter(
        [
            "run-1",
            "stage-thematic",
            "stage-regulatory",
            "stage-strategic",
            "run-2",
            "stage-2-thematic",
            "stage-2-regulatory",
            "stage-2-strategic",
        ]
    )
    return lambda: next(ids)


def repository_with_client():
    client = FakeClient()
    return (
        SupabaseAnalysisRunRepository(
            settings=settings(),
            client=client,
            uuid_factory=id_factory(),
            clock=lambda: NOW,
        ),
        client,
    )


def complete_all_stages(repository: SupabaseAnalysisRunRepository, run_id: str) -> None:
    repository.update_run_status(run_id, AnalysisRunStatus.RUNNING)
    for stage in (
        AnalysisStage.THEMATIC_LANDSCAPE,
        AnalysisStage.REGULATORY_INTELLIGENCE,
        AnalysisStage.STRATEGIC_ASSESSMENT,
    ):
        repository.update_stage_status(run_id, stage, AnalysisRunStatus.RUNNING)
        repository.save_stage_result(run_id, stage, {"stage": stage.value})
        repository.update_stage_status(run_id, stage, AnalysisRunStatus.COMPLETED)
    repository.update_run_status(run_id, AnalysisRunStatus.COMPLETED)


def test_creates_run_with_ordered_default_stages_and_rejects_concurrent_run():
    repository, _client = repository_with_client()

    run = repository.create_run("snapshot-1")

    assert run.id == "run-1"
    assert run.status == AnalysisRunStatus.QUEUED
    assert [stage.stage for stage in repository.list_stages(run.id)] == [
        AnalysisStage.THEMATIC_LANDSCAPE,
        AnalysisStage.REGULATORY_INTELLIGENCE,
        AnalysisStage.STRATEGIC_ASSESSMENT,
    ]
    with pytest.raises(ConcurrentAnalysisRunError):
        repository.create_run("snapshot-1")


def test_completes_and_publishes_run_using_rpc():
    repository, _client = repository_with_client()
    run = repository.create_run("snapshot-1")

    with pytest.raises(IncompleteAnalysisPublicationError):
        repository.publish_run(run.id)

    complete_all_stages(repository, run.id)
    published = repository.publish_run(run.id)

    assert published.status == AnalysisRunStatus.PUBLISHED
    assert published.published_at == NOW
    assert repository.get_latest_published_run() == published


def test_retry_failed_stage_resets_target_and_later_stages():
    repository, _client = repository_with_client()
    run = repository.create_run("snapshot-1")
    repository.update_run_status(run.id, AnalysisRunStatus.RUNNING)
    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
    )
    repository.save_stage_result(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, {"ok": True}
    )
    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.FAILED
    )

    stages = repository.prepare_stage_retry(run.id, AnalysisStage.THEMATIC_LANDSCAPE)

    assert [stage.status for stage in stages] == [
        AnalysisRunStatus.QUEUED,
        AnalysisRunStatus.QUEUED,
        AnalysisRunStatus.QUEUED,
    ]
    assert all(stage.result_payload is None for stage in stages)
    with pytest.raises(InvalidAnalysisRetryError):
        repository.prepare_stage_retry(run.id, AnalysisStage.THEMATIC_LANDSCAPE)


def test_active_run_can_be_marked_failed_for_retry():
    repository, _client = repository_with_client()
    run = repository.create_run("snapshot-1")
    repository.update_run_status(run.id, AnalysisRunStatus.RUNNING)
    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
    )

    assert repository.get_active_run_for_snapshot("snapshot-1").id == run.id
    assert repository.get_latest_active_run().id == run.id

    failed = repository.fail_incomplete_run_for_retry(
        run.id, error_message="recover stale run"
    )

    assert failed.status == AnalysisRunStatus.FAILED
    assert repository.get_stage(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE
    ).status == AnalysisRunStatus.FAILED
    assert repository.get_active_run_for_snapshot("snapshot-1") is None
    stages = repository.prepare_stage_retry(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE
    )
    assert [stage.status for stage in stages] == [
        AnalysisRunStatus.QUEUED,
        AnalysisRunStatus.QUEUED,
        AnalysisRunStatus.QUEUED,
    ]


def test_empty_lookup_and_missing_configuration():
    repository, _client = repository_with_client()

    assert repository.get_run("missing") is None
    assert repository.get_stage("missing", AnalysisStage.THEMATIC_LANDSCAPE) is None
    assert repository.get_latest_published_run() is None

    missing_config = SupabaseAnalysisRunRepository(
        settings=load_settings(environ={"SUPABASE_URL": "", "SUPABASE_KEY": ""})
    )
    with pytest.raises(StorageConfigurationError):
        missing_config.get_run("run")
