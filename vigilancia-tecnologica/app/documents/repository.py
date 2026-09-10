"""Interfaces de persistencia para el dominio documental."""

from __future__ import annotations

from typing import Protocol

from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    ProcessingJob,
    JobStatus,
)


class DocumentRepository(Protocol):
    """Contrato de persistencia sin acoplarse a Supabase."""

    def save_document(self, document: Document) -> Document:
        """Guarda un documento nuevo."""

    def get_document(self, document_id: str) -> Document | None:
        """Obtiene un documento por ID."""

    def find_document_by_hash(self, file_hash: str) -> Document | None:
        """Busca un documento por hash de archivo."""

    def update_document_status(
        self, document_id: str, status: DocumentStatus
    ) -> Document:
        """Actualiza el estado de un documento."""

    def save_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        """Guarda un chunk documental."""

    def list_chunks(self, document_id: str) -> list[DocumentChunk]:
        """Lista chunks de un documento en orden de posicion."""

    def create_job(self, job: ProcessingJob) -> ProcessingJob:
        """Crea un job de procesamiento."""

    def get_job(self, job_id: str) -> ProcessingJob | None:
        """Obtiene un job por ID."""

    def list_jobs(self, document_id: str) -> list[ProcessingJob]:
        """Lista jobs asociados a un documento."""

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_message: str | None = None,
    ) -> ProcessingJob:
        """Actualiza el estado de un job."""
