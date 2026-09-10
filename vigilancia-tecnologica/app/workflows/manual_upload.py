"""Workflow de carga manual hacia Storage y registro documental."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from app.documents.models import Document
from app.documents.models import DocumentStatus
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentRegistration, DocumentService
from app.storage.repository import SourceDocumentStorage, StoredSourceDocument


class ManualDocumentUploadError(Exception):
    """Fallo controlado durante carga manual."""


@dataclass(frozen=True)
class ManualDocumentUploadResult:
    registration: DocumentRegistration
    stored_document: StoredSourceDocument | None

    @property
    def document(self) -> Document:
        return self.registration.document

    @property
    def is_duplicate(self) -> bool:
        return self.registration.is_duplicate


class ManualDocumentUploadService:
    """Sube el original y registra el documento con `storage_path` real."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        document_service: DocumentService,
        storage: SourceDocumentStorage,
        uuid_factory: Callable[[], str] | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._document_service = document_service
        self._storage = storage
        self._uuid_factory = uuid_factory or (lambda: str(uuid4()))

    def upload(
        self,
        *,
        file_name: str,
        content: bytes,
        source_type,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
        document_date: date | None = None,
        replaces_id: str | None = None,
        reuse_uploaded_duplicate: bool = False,
    ) -> ManualDocumentUploadResult:
        file_hash = DocumentService.calculate_sha256(content)
        existing = self._document_repository.find_document_by_hash(file_hash)
        if existing is not None:
            is_reusable = (
                reuse_uploaded_duplicate
                and existing.status == DocumentStatus.UPLOADED
                and existing.source_type == source_type
                and existing.storage_path is not None
            )
            return ManualDocumentUploadResult(
                registration=DocumentRegistration(
                    document=existing,
                    job=None,
                    is_duplicate=not is_reusable,
                ),
                stored_document=None,
            )

        document_id = self._uuid_factory()
        stored = self._storage.upload_source_document(
            source_type=source_type.value,
            document_id=document_id,
            file_name=file_name,
            content=content,
            content_type=content_type or _guess_content_type(file_name),
        )
        try:
            registration = self._document_service.register_document(
                file_name=file_name,
                file_type=_file_type(file_name),
                source_type=source_type,
                content=content,
                storage_path=stored.path,
                document_date=document_date,
                replaces_id=replaces_id,
                document_id=document_id,
                provider=(metadata or {}).get("provider"),
            )
        except Exception as exc:
            self._storage.delete_source_document(stored.path)
            raise ManualDocumentUploadError(
                f"No fue posible registrar {file_name} despues de subirlo."
            ) from exc

        return ManualDocumentUploadResult(
            registration=registration,
            stored_document=stored,
        )


def _file_type(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    return extension.lstrip(".")


def _guess_content_type(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    if extension == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if extension == ".xls":
        return "application/vnd.ms-excel"
    if extension == ".pdf":
        return "application/pdf"
    guessed, _encoding = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"
