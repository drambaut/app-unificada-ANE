"""Pruebas del repositorio Supabase de snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.settings import load_settings
from app.corpus_snapshots.errors import DuplicateCorpusSnapshotError
from app.corpus_snapshots.models import CorpusSnapshot, SnapshotRecordRef
from app.corpus_snapshots.supabase_repository import SupabaseCorpusSnapshotRepository
from app.storage.errors import StorageConfigurationError


NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
HASH = "a" * 64


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


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str):
        return self.tables.setdefault(name, FakeTable())


def settings():
    return load_settings(
        environ={
            "DATA_DIR": "../data",
            "OUTPUT_DIR": "outputs",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "test-key",
        }
    )


def make_snapshot(snapshot_id: str = "snapshot-1") -> CorpusSnapshot:
    snapshot_hash = f"{snapshot_id}-{HASH}"[:64].ljust(64, "a")
    return CorpusSnapshot(
        id=snapshot_id,
        created_at=NOW,
        snapshot_hash=snapshot_hash,
        selection_criteria={"status": "processed"},
        surveillance_document_ids=("doc-surv",),
        institutional_plan_document_ids=("doc-plan",),
        policy_matrix_document_ids=("doc-policy",),
        record_refs=(
            SnapshotRecordRef(
                record_id="record-1",
                document_id="doc-surv",
                record_type="finding",
                canonical_key="finding|doc",
                content_hash=HASH,
                record_version="v1",
                created_at=NOW,
            ),
        ),
        metadata={"kind": "test"},
    )


def repository_with_client():
    client = FakeClient()
    return SupabaseCorpusSnapshotRepository(settings=settings(), client=client), client


def test_saves_and_reads_snapshot_with_documents_and_refs():
    repository, client = repository_with_client()
    snapshot = make_snapshot()

    saved = repository.save_snapshot(snapshot)
    loaded = repository.get_snapshot(snapshot.id)

    assert saved == snapshot
    assert loaded == snapshot
    assert {row["source_type"] for row in client.table("corpus_snapshot_documents").rows} == {
        "surveillance",
        "institutional_plan",
        "policy_matrix",
    }
    assert client.table("corpus_snapshot_record_refs").rows[0]["record_version"] == "v1"


def test_rejects_duplicate_snapshot_id_and_lists_by_created_at():
    repository, _client = repository_with_client()
    first = make_snapshot("snapshot-1")
    second = make_snapshot("snapshot-2")
    repository.save_snapshot(first)
    repository.save_snapshot(second)

    with pytest.raises(DuplicateCorpusSnapshotError):
        repository.save_snapshot(first)

    assert repository.list_snapshots() == [first, second]


def test_reuses_existing_snapshot_when_hash_already_exists():
    repository, client = repository_with_client()
    first = make_snapshot("snapshot-1")
    retry = make_snapshot("snapshot-retry")
    retry = CorpusSnapshot(
        id=retry.id,
        created_at=retry.created_at,
        snapshot_hash=first.snapshot_hash,
        selection_criteria=retry.selection_criteria,
        surveillance_document_ids=retry.surveillance_document_ids,
        institutional_plan_document_ids=retry.institutional_plan_document_ids,
        policy_matrix_document_ids=retry.policy_matrix_document_ids,
        record_refs=retry.record_refs,
        metadata=retry.metadata,
    )

    repository.save_snapshot(first)
    saved_retry = repository.save_snapshot(retry)

    assert saved_retry == first
    assert len(client.table("corpus_snapshots").rows) == 1


def test_empty_lookup_and_missing_configuration():
    repository, _client = repository_with_client()

    assert repository.get_snapshot("missing") is None

    missing_config = SupabaseCorpusSnapshotRepository(
        settings=load_settings(environ={"SUPABASE_URL": "", "SUPABASE_KEY": ""})
    )
    with pytest.raises(StorageConfigurationError):
        missing_config.get_snapshot("snapshot")
