"""Pruebas del workflow de carga manual."""

from __future__ import annotations

from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import SourceType
from app.documents.service import DocumentService
from app.storage.repository import StoredSourceDocument
from app.workflows.manual_upload import (
    ManualDocumentUploadError,
    ManualDocumentUploadService,
)


class FakeStorage:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.uploads = []
        self.deleted = []
        self.fail_delete = fail_delete

    def upload_source_document(
        self,
        *,
        source_type: str,
        document_id: str,
        file_name: str,
        content: bytes,
        content_type: str,
        upsert: bool = False,
    ) -> StoredSourceDocument:
        path = f"{source_type}/{document_id}/{file_name}"
        self.uploads.append(
            {
                "source_type": source_type,
                "document_id": document_id,
                "file_name": file_name,
                "content": content,
                "content_type": content_type,
                "upsert": upsert,
                "path": path,
            }
        )
        return StoredSourceDocument(
            bucket="source-documents",
            path=path,
            content_type=content_type,
            size_bytes=len(content),
        )

    def download_source_document(self, path: str) -> bytes:
        raise NotImplementedError

    def delete_source_document(self, path: str) -> None:
        self.deleted.append(path)
        if self.fail_delete:
            raise RuntimeError("delete failed")


class FailingDocumentService:
    def register_document(self, **_kwargs):
        raise RuntimeError("db failed")


def make_service(repository=None, storage=None):
    repository = repository or InMemoryDocumentRepository()
    document_service = DocumentService(repository)
    storage = storage or FakeStorage()
    service = ManualDocumentUploadService(
        document_repository=repository,
        document_service=document_service,
        storage=storage,
        uuid_factory=lambda: "doc-1",
    )
    return service, repository, storage


def test_uploads_original_and_registers_document_with_storage_path():
    service, repository, storage = make_service()

    result = service.upload(
        file_name="reporte.pdf",
        content=b"%PDF",
        source_type=SourceType.SURVEILLANCE,
    )

    assert result.is_duplicate is False
    assert result.document.id == "doc-1"
    assert result.document.storage_path == "surveillance/doc-1/reporte.pdf"
    assert result.registration.job is not None
    assert result.stored_document.path == result.document.storage_path
    assert storage.uploads[0]["content_type"] == "application/pdf"
    assert repository.get_document("doc-1") == result.document


def test_upload_uses_excel_content_type_for_xlsx():
    service, _repository, storage = make_service()

    service.upload(
        file_name="matriz.xlsx",
        content=b"xlsx",
        source_type=SourceType.SURVEILLANCE,
    )

    assert storage.uploads[0]["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_duplicate_upload_reuses_existing_document_without_storage_write():
    service, _repository, storage = make_service()
    first = service.upload(
        file_name="reporte.pdf",
        content=b"same",
        source_type=SourceType.SURVEILLANCE,
    )

    second = service.upload(
        file_name="otro.pdf",
        content=b"same",
        source_type=SourceType.SURVEILLANCE,
    )

    assert second.is_duplicate is True
    assert second.document == first.document
    assert second.stored_document is None
    assert len(storage.uploads) == 1


def test_uploaded_duplicate_can_be_reused_for_explicit_retry():
    service, _repository, storage = make_service()
    first = service.upload(
        file_name="reporte.pdf",
        content=b"same",
        source_type=SourceType.SURVEILLANCE,
    )

    retry = service.upload(
        file_name="reporte.pdf",
        content=b"same",
        source_type=SourceType.SURVEILLANCE,
        reuse_uploaded_duplicate=True,
    )

    assert retry.is_duplicate is False
    assert retry.document == first.document
    assert retry.stored_document is None
    assert len(storage.uploads) == 1


def test_upload_cleans_storage_if_registration_fails():
    repository = InMemoryDocumentRepository()
    storage = FakeStorage()
    service = ManualDocumentUploadService(
        document_repository=repository,
        document_service=FailingDocumentService(),
        storage=storage,
        uuid_factory=lambda: "doc-1",
    )

    try:
        service.upload(
            file_name="reporte.pdf",
            content=b"%PDF",
            source_type=SourceType.SURVEILLANCE,
        )
    except ManualDocumentUploadError:
        pass
    else:
        raise AssertionError("ManualDocumentUploadError was not raised")

    assert storage.deleted == ["surveillance/doc-1/reporte.pdf"]
    assert repository.get_document("doc-1") is None
