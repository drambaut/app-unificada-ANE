"""Pruebas del repositorio documental Supabase."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.settings import load_settings
from app.documents.errors import DocumentNotFoundError, DuplicateDocumentError
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    JobType,
    ProcessingJob,
    SourceType,
)
from app.documents.supabase_repository import SupabaseDocumentRepository
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


class FakeClient:
    def __init__(self) -> None:
        self.tables = {
            "documents": FakeTable(),
            "document_chunks": FakeTable(),
            "processing_jobs": FakeTable(),
        }

    def table(self, name: str):
        return self.tables[name]


def settings():
    return load_settings(
        environ={
            "DATA_DIR": "../data",
            "OUTPUT_DIR": "outputs",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "test-key",
        }
    )


def make_document(**overrides) -> Document:
    document = Document(
        id="11111111-1111-4111-8111-111111111111",
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        file_hash="hash-1",
        storage_path="surveillance/doc/doc.pdf",
        document_date=None,
        status=DocumentStatus.UPLOADED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    return replace(document, **overrides)


def make_chunk(**overrides) -> DocumentChunk:
    chunk = DocumentChunk(
        id="22222222-2222-4222-8222-222222222222",
        document_id="11111111-1111-4111-8111-111111111111",
        content="contenido",
        page_number=1,
        section_title=None,
        sheet_name=None,
        row_reference=None,
        content_hash="hash-chunk",
        position=1,
    )
    return replace(chunk, **overrides)


def make_job(**overrides) -> ProcessingJob:
    job = ProcessingJob(
        id="33333333-3333-4333-8333-333333333333",
        document_id="11111111-1111-4111-8111-111111111111",
        job_type=JobType.DOCUMENT_PREPARATION,
        status=JobStatus.QUEUED,
        prompt_id=None,
        prompt_version=None,
        attempts=0,
        error_message=None,
        created_at=NOW,
        completed_at=None,
    )
    return replace(job, **overrides)


def repository_with_client():
    client = FakeClient()
    return SupabaseDocumentRepository(settings=settings(), client=client), client


def test_saves_and_finds_document_by_id_and_hash():
    repository, client = repository_with_client()
    document = make_document()

    saved = repository.save_document(document)

    assert saved == document
    assert client.tables["documents"].rows[0]["storage_bucket"] == "source-documents"
    assert repository.get_document(document.id) == document
    assert repository.find_document_by_hash(document.file_hash) == document


def test_rejects_duplicate_hash_for_different_document():
    repository, _client = repository_with_client()
    repository.save_document(make_document())

    with pytest.raises(DuplicateDocumentError):
        repository.save_document(
            make_document(
                id="44444444-4444-4444-8444-444444444444",
            )
        )


def test_updates_document_status():
    repository, _client = repository_with_client()
    document = repository.save_document(make_document())

    updated = repository.update_document_status(document.id, DocumentStatus.PREPARING)

    assert updated.status == DocumentStatus.PREPARING


def test_lists_only_processed_documents_ordered_by_creation():
    repository, _client = repository_with_client()
    first = repository.save_document(
        make_document(
            id="doc-1",
            file_hash="hash-1",
            status=DocumentStatus.PROCESSED,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    repository.save_document(
        make_document(
            id="doc-2",
            file_hash="hash-2",
            status=DocumentStatus.UPLOADED,
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    second = repository.save_document(
        make_document(
            id="doc-3",
            file_hash="hash-3",
            status=DocumentStatus.PROCESSED,
            created_at=datetime(2026, 1, 3, tzinfo=UTC),
            updated_at=datetime(2026, 1, 3, tzinfo=UTC),
        )
    )

    assert repository.list_processed_documents() == [first, second]


def test_chunks_are_listed_by_position_and_require_document():
    repository, _client = repository_with_client()
    document = repository.save_document(make_document())
    repository.save_chunk(make_chunk(document_id=document.id, id="chunk-2", position=2))
    repository.save_chunk(make_chunk(document_id=document.id, id="chunk-1", position=1))

    assert [chunk.id for chunk in repository.list_chunks(document.id)] == [
        "chunk-1",
        "chunk-2",
    ]
    with pytest.raises(DocumentNotFoundError):
        repository.save_chunk(make_chunk(document_id="missing"))


def test_jobs_can_be_created_listed_and_completed():
    repository, _client = repository_with_client()
    document = repository.save_document(make_document())
    first = repository.create_job(make_job(document_id=document.id, id="job-1"))
    second = repository.create_job(
        make_job(
            document_id=document.id,
            id="job-2",
            job_type=JobType.DOCUMENT_ANALYSIS,
            created_at=datetime(2026, 1, 2, 3, 5, tzinfo=UTC),
        )
    )

    completed = repository.update_job_status(first.id, JobStatus.COMPLETED)

    assert completed.status == JobStatus.COMPLETED
    assert completed.completed_at is not None
    assert repository.get_job(second.id) == second
    assert [job.id for job in repository.list_jobs(document.id)] == ["job-1", "job-2"]


def test_missing_supabase_configuration_is_reported():
    repository = SupabaseDocumentRepository(
        settings=load_settings(environ={"SUPABASE_URL": "", "SUPABASE_KEY": ""})
    )

    with pytest.raises(StorageConfigurationError):
        repository.get_document("doc")
