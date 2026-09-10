"""Pruebas de repositorios Supabase de lectura para dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

from app.dashboard_read.supabase_repositories import (
    SupabaseDashboardDocumentReadRepository,
    SupabaseDashboardResultReadRepository,
)
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle


NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeDocumentRepository:
    def __init__(self, documents: dict[str, Document]) -> None:
        self.documents = documents
        self.requested: list[str] = []

    def get_document(self, document_id: str):
        self.requested.append(document_id)
        return self.documents.get(document_id)


class FakeResultRepository:
    def __init__(self, bundles: dict[str, PersistenceBundle]) -> None:
        self.bundles = bundles
        self.requested: list[str] = []

    def get_bundle(self, document_id: str):
        self.requested.append(document_id)
        return self.bundles.get(document_id)


def document(document_id: str) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        file_hash=f"hash-{document_id}",
        storage_path=f"surveillance/{document_id}/{document_id}.pdf",
        document_date=None,
        status=DocumentStatus.PROCESSED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def test_document_reader_delegates_and_filters_missing_documents():
    doc_1 = document("doc-1")
    fake = FakeDocumentRepository({"doc-1": doc_1})
    reader = SupabaseDashboardDocumentReadRepository(document_repository=fake)

    assert reader.get_documents_by_ids(["doc-1", "missing"]) == [doc_1]
    assert fake.requested == ["doc-1", "missing"]


def test_result_reader_delegates_and_filters_missing_bundles():
    bundle = PersistenceBundle(document_id="doc-1")
    fake = FakeResultRepository({"doc-1": bundle})
    reader = SupabaseDashboardResultReadRepository(result_repository=fake)

    assert reader.get_bundles_by_document_ids(["doc-1", "missing"]) == [bundle]
    assert fake.requested == ["doc-1", "missing"]
