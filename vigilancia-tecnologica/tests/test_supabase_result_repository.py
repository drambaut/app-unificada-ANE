"""Pruebas del repositorio Supabase de resultados normalizados."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.settings import load_settings
from app.results.errors import DuplicateResultError, ResultPersistenceError
from app.results.models import PersistenceBundle, ResultRecord
from app.results.supabase_repository import SupabaseResultRepository
from app.storage.errors import StorageConfigurationError


NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
DOCUMENT_ID = "11111111-1111-4111-8111-111111111111"


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


class FakeRpc:
    def __init__(self, client: "FakeClient", name: str, params: dict[str, Any]) -> None:
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        assert self.name == "persist_result_bundle"
        bundle = self.params["bundle"]
        for parent in bundle["result_records"]:
            self.client.table("result_records").rows.append(dict(parent))
        for child in bundle["child_records"]:
            self.client.table(child["table"]).rows.append(dict(child["data"]))
        for link in bundle["evidence_links"]:
            self.client.table("result_record_evidence").rows.append(dict(link))
        return FakeResponse([None])


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str):
        return self.tables.setdefault(name, FakeTable())

    def rpc(self, name: str, params: dict[str, Any]):
        self.rpc_calls.append((name, params))
        return FakeRpc(self, name, params)


class FailingRpc:
    def execute(self):
        raise RuntimeError("rpc failed")


class FailingRpcClient(FakeClient):
    def rpc(self, name: str, params: dict[str, Any]):
        self.rpc_calls.append((name, params))
        return FailingRpc()


def settings():
    return load_settings(
        environ={
            "DATA_DIR": "../data",
            "OUTPUT_DIR": "outputs",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "test-key",
        }
    )


def record(record_id: str, data: dict[str, Any], canonical_key: str) -> ResultRecord:
    return ResultRecord(
        id=record_id,
        document_id=DOCUMENT_ID,
        data=data,
        prompt_id="document_extraction",
        prompt_version="v1",
        contract_name="DocumentExtraction",
        model_name="gemini-test",
        created_at=NOW,
        canonical_key=canonical_key,
        confidence="Alta",
        extraction_basis="explicit",
    )


def make_bundle() -> PersistenceBundle:
    evidence = record(
        "evidence-1",
        {
            "quote": "Texto citado",
            "evidence_type": "page",
            "page_number": 1,
            "matched_chunk_id": "chunk-1",
        },
        "evidence|doc|chunk-1|texto citado",
    )
    finding = record(
        "finding-1",
        {
            "finding_type": "trend",
            "title": "6G",
            "description": "Avance regulatorio",
            "evidence_ids": ["evidence-1"],
            "technologies": ["6G"],
        },
        "finding|doc|6g|trend",
    )
    analysis = record(
        "analysis-1",
        {
            "document_type": "reporte",
            "title": "Reporte",
            "summary": "Resumen",
            "technologies": ["6G"],
        },
        "document_analysis|doc",
    )
    return PersistenceBundle(
        document_id=DOCUMENT_ID,
        document_analysis=analysis,
        findings=[finding],
        evidence=[evidence],
    )


def repository_with_client():
    client = FakeClient()
    return SupabaseResultRepository(settings=settings(), client=client), client


def test_saves_parent_child_rows_and_evidence_relations():
    repository, client = repository_with_client()
    bundle = make_bundle()

    saved = repository.save_bundle(bundle)

    assert saved == bundle
    assert [name for name, _params in client.rpc_calls] == ["persist_result_bundle"]
    assert [row["record_type"] for row in client.table("result_records").rows] == [
        "document_analysis",
        "finding",
        "evidence",
    ]
    assert client.table("document_analysis").rows[0]["title"] == "Reporte"
    assert client.table("findings").rows[0]["title"] == "6G"
    assert client.table("evidence").rows[0]["matched_chunk_id"] == "chunk-1"
    assert client.table("result_record_evidence").rows == [
        {"record_id": "finding-1", "evidence_id": "evidence-1"}
    ]
    assert len(client.table("result_records").rows[0]["content_hash"]) == 64
    assert client.table("result_records").rows[0]["record_version"] == NOW.isoformat()


def test_reads_bundle_from_parent_rows_grouped_by_type():
    repository, _client = repository_with_client()
    bundle = make_bundle()
    repository.save_bundle(bundle)

    loaded = repository.get_bundle(DOCUMENT_ID)

    assert loaded == bundle


def test_rejects_duplicate_document_and_canonical_key():
    repository, _client = repository_with_client()
    bundle = make_bundle()
    repository.save_bundle(bundle)

    with pytest.raises(DuplicateResultError):
        repository.save_bundle(bundle)

    other_document_bundle = replace(
        bundle,
        document_id="22222222-2222-4222-8222-222222222222",
        document_analysis=replace(
            bundle.document_analysis,
            id="analysis-2",
            document_id="22222222-2222-4222-8222-222222222222",
        ),
    )
    with pytest.raises(DuplicateResultError):
        repository.save_bundle(other_document_bundle)


def test_has_canonical_key_and_empty_bundle_lookup():
    repository, _client = repository_with_client()

    assert repository.get_bundle("missing") is None
    assert repository.has_canonical_key("missing") is False

    repository.save_bundle(make_bundle())

    assert repository.has_canonical_key("document_analysis|doc") is True


def test_rpc_failure_is_reported_without_local_partial_writes():
    client = FailingRpcClient()
    repository = SupabaseResultRepository(settings=settings(), client=client)

    with pytest.raises(ResultPersistenceError, match="No fue posible persistir resultados"):
        repository.save_bundle(make_bundle())

    assert client.table("result_records").rows == []


def test_missing_supabase_configuration_is_reported():
    repository = SupabaseResultRepository(
        settings=load_settings(environ={"SUPABASE_URL": "", "SUPABASE_KEY": ""})
    )

    with pytest.raises(StorageConfigurationError):
        repository.get_bundle("doc")
