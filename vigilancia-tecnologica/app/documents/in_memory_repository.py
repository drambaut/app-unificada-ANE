"""Repositorio en memoria para pruebas del dominio documental."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.documents.errors import (
    DuplicateDocumentError,
    DocumentNotFoundError,
    ProcessingJobNotFoundError,
)
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    ProcessingJob,
)


class InMemoryDocumentRepository:
    """Implementacion no persistente, sin escritura de archivos."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._documents_by_hash: dict[str, str] = {}
        self._chunks: dict[str, list[DocumentChunk]] = {}
        self._jobs: dict[str, ProcessingJob] = {}
        self._jobs_by_document: dict[str, list[str]] = {}

    def save_document(self, document: Document) -> Document:
        existing_id = self._documents_by_hash.get(document.file_hash)
        if existing_id is not None and existing_id != document.id:
            raise DuplicateDocumentError(
                f"Ya existe un documento con hash {document.file_hash}."
            )
        self._documents[document.id] = document
        self._documents_by_hash[document.file_hash] = document.id
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def find_document_by_hash(self, file_hash: str) -> Document | None:
        document_id = self._documents_by_hash.get(file_hash)
        return self._documents.get(document_id) if document_id is not None else None

    def update_document_status(
        self, document_id: str, status: DocumentStatus
    ) -> Document:
        document = self.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")
        updated = replace(document, status=status, updated_at=datetime.now(UTC))
        self._documents[document_id] = updated
        return updated

    def save_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        if chunk.document_id not in self._documents:
            raise DocumentNotFoundError(f"No existe el documento {chunk.document_id}.")
        self._chunks.setdefault(chunk.document_id, []).append(chunk)
        self._chunks[chunk.document_id].sort(key=lambda item: item.position)
        return chunk

    def list_chunks(self, document_id: str) -> list[DocumentChunk]:
        return list(self._chunks.get(document_id, []))

    def create_job(self, job: ProcessingJob) -> ProcessingJob:
        if job.document_id not in self._documents:
            raise DocumentNotFoundError(f"No existe el documento {job.document_id}.")
        self._jobs[job.id] = job
        self._jobs_by_document.setdefault(job.document_id, []).append(job.id)
        return job

    def get_job(self, job_id: str) -> ProcessingJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self, document_id: str) -> list[ProcessingJob]:
        return [
            self._jobs[job_id]
            for job_id in self._jobs_by_document.get(document_id, [])
        ]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_message: str | None = None,
    ) -> ProcessingJob:
        job = self.get_job(job_id)
        if job is None:
            raise ProcessingJobNotFoundError(f"No existe el job {job_id}.")
        completed_at = datetime.now(UTC) if status in {JobStatus.COMPLETED, JobStatus.FAILED} else None
        updated = replace(
            job,
            status=status,
            error_message=error_message,
            completed_at=completed_at,
        )
        self._jobs[job_id] = updated
        return updated
