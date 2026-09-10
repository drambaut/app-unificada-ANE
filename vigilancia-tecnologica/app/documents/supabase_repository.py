"""Repositorio documental sobre Supabase/PostgREST."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Callable

from app.core.settings import Settings, load_settings
from app.documents.errors import (
    DocumentDomainError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    ProcessingJobNotFoundError,
)
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    JobType,
    ProcessingJob,
    SourceType,
)
from app.storage.errors import StorageConfigurationError


class SupabaseDocumentRepository:
    """Implementacion Supabase del contrato `DocumentRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client
        self._client_factory = client_factory

    def save_document(self, document: Document) -> Document:
        existing = self.find_document_by_hash(document.file_hash)
        if existing is not None and existing.id != document.id:
            raise DuplicateDocumentError(
                f"Ya existe un documento con hash {document.file_hash}."
            )
        row = self._insert("documents", self._document_to_row(document))
        return _document_from_row(row)

    def get_document(self, document_id: str) -> Document | None:
        row = self._single(
            self._table("documents")
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
            .data
        )
        return _document_from_row(row) if row is not None else None

    def find_document_by_hash(self, file_hash: str) -> Document | None:
        row = self._single(
            self._table("documents")
            .select("*")
            .eq("file_hash", file_hash)
            .limit(1)
            .execute()
            .data
        )
        return _document_from_row(row) if row is not None else None

    def list_processed_documents(self) -> list[Document]:
        rows = (
            self._table("documents")
            .select("*")
            .eq("status", DocumentStatus.PROCESSED.value)
            .order("created_at")
            .execute()
            .data
        )
        return [_document_from_row(row) for row in rows or []]

    def update_document_status(
        self, document_id: str, status: DocumentStatus
    ) -> Document:
        row = self._single(
            self._table("documents")
            .update({"status": status.value})
            .eq("id", document_id)
            .execute()
            .data
        )
        if row is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")
        return _document_from_row(row)

    def update_document_provider(self, document_id: str, provider: str) -> Document:
        row = self._single(
            self._table("documents")
            .update({"provider": provider})
            .eq("id", document_id)
            .execute()
            .data
        )
        if row is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")
        return _document_from_row(row)

    def save_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        self._require_document(chunk.document_id)
        row = self._insert("document_chunks", _chunk_to_row(chunk))
        return _chunk_from_row(row)

    def list_chunks(self, document_id: str) -> list[DocumentChunk]:
        rows = (
            self._table("document_chunks")
            .select("*")
            .eq("document_id", document_id)
            .order("position")
            .execute()
            .data
        )
        return [_chunk_from_row(row) for row in rows or []]

    def match_chunks(
        self,
        *,
        query_embedding: list[float],
        match_threshold: float,
        match_count: int,
        document_ids: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Realiza búsqueda semántica de fragmentos usando la función RPC en la base de datos."""
        params = {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count,
        }
        if document_ids is not None:
            params["filter_document_ids"] = document_ids
        
        rows = (
            self._client.rpc("match_document_chunks", params)
            .execute()
            .data
        )
        return [_chunk_from_row(row) for row in rows or []]

    def create_job(self, job: ProcessingJob) -> ProcessingJob:
        self._require_document(job.document_id)
        row = self._insert("processing_jobs", _job_to_row(job))
        return _job_from_row(row)

    def get_job(self, job_id: str) -> ProcessingJob | None:
        row = self._single(
            self._table("processing_jobs")
            .select("*")
            .eq("id", job_id)
            .limit(1)
            .execute()
            .data
        )
        return _job_from_row(row) if row is not None else None

    def list_jobs(self, document_id: str) -> list[ProcessingJob]:
        rows = (
            self._table("processing_jobs")
            .select("*")
            .eq("document_id", document_id)
            .order("created_at")
            .execute()
            .data
        )
        return [_job_from_row(row) for row in rows or []]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_message: str | None = None,
    ) -> ProcessingJob:
        payload: dict[str, Any] = {
            "status": status.value,
            "error_message": error_message,
        }
        if status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            payload["completed_at"] = datetime.now(UTC).isoformat()
        else:
            payload["completed_at"] = None
        row = self._single(
            self._table("processing_jobs")
            .update(payload)
            .eq("id", job_id)
            .execute()
            .data
        )
        if row is None:
            raise ProcessingJobNotFoundError(f"No existe el job {job_id}.")
        return _job_from_row(row)

    def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self._single(self._table(table).insert(payload).execute().data)
        if row is None:
            raise DocumentDomainError(f"Supabase no retorno fila al insertar {table}.")
        return row

    def _require_document(self, document_id: str) -> Document:
        document = self.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")
        return document

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

    @staticmethod
    def _single(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
        if not rows:
            return None
        return rows[0]

    def _document_to_row(self, document: Document) -> dict[str, Any]:
        row = _document_to_row(document)
        if document.storage_path:
            row["storage_bucket"] = self._settings.supabase_storage_bucket
        return row


def _document_to_row(document: Document) -> dict[str, Any]:
    return {
        "id": document.id,
        "file_name": document.file_name,
        "file_type": document.file_type,
        "source_type": document.source_type.value,
        "file_hash": document.file_hash,
        "storage_path": document.storage_path,
        "document_date": document.document_date.isoformat()
        if document.document_date
        else None,
        "status": document.status.value,
        "version": document.version,
        "replaces_id": document.replaces_id,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
        "provider": document.provider,
    }


def _document_from_row(row: dict[str, Any]) -> Document:
    return Document(
        id=row["id"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        source_type=SourceType(row["source_type"]),
        file_hash=row["file_hash"],
        storage_path=row.get("storage_path"),
        document_date=_parse_date(row.get("document_date")),
        status=DocumentStatus(row["status"]),
        version=row["version"],
        replaces_id=row.get("replaces_id"),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        provider=row.get("provider"),
    )


def _chunk_to_row(chunk: DocumentChunk) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "content": chunk.content,
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "sheet_name": chunk.sheet_name,
        "row_reference": chunk.row_reference,
        "content_hash": chunk.content_hash,
        "position": chunk.position,
    }
    if chunk.embedding is not None:
        row["embedding"] = chunk.embedding
    return row


def _chunk_from_row(row: dict[str, Any]) -> DocumentChunk:
    return DocumentChunk(
        id=row["id"],
        document_id=row["document_id"],
        content=row["content"],
        page_number=row.get("page_number"),
        section_title=row.get("section_title"),
        sheet_name=row.get("sheet_name"),
        row_reference=row.get("row_reference"),
        content_hash=row["content_hash"],
        position=row["position"],
        embedding=row.get("embedding"),
    )


def _job_to_row(job: ProcessingJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "prompt_id": job.prompt_id,
        "prompt_version": job.prompt_version,
        "attempts": job.attempts,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _job_from_row(row: dict[str, Any]) -> ProcessingJob:
    return ProcessingJob(
        id=row["id"],
        document_id=row["document_id"],
        job_type=JobType(row["job_type"]),
        status=JobStatus(row["status"]),
        prompt_id=row.get("prompt_id"),
        prompt_version=row.get("prompt_version"),
        attempts=row["attempts"],
        error_message=row.get("error_message"),
        created_at=_parse_datetime(row["created_at"]),
        completed_at=_parse_datetime(row.get("completed_at")),
    )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)
