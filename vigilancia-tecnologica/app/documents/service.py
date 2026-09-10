"""Servicios de dominio para documentos y procesamiento."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from app.documents.errors import (
    DuplicateProcessingJobError,
    DocumentNotFoundError,
    InvalidDocumentStatusTransition,
    InvalidProcessingJobSequence,
)
from app.documents.models import (
    Document,
    DocumentStatus,
    JobStatus,
    JobType,
    ProcessingJob,
    SourceType,
)
from app.documents.repository import DocumentRepository


ANALYSIS_JOB_BY_SOURCE_TYPE: dict[SourceType, JobType] = {
    SourceType.SURVEILLANCE: JobType.DOCUMENT_ANALYSIS,
    SourceType.INSTITUTIONAL_PLAN: JobType.INSTITUTIONAL_PLAN_ANALYSIS,
    SourceType.POLICY_MATRIX: JobType.POLICY_MATRIX_ANALYSIS,
    # Los nuevos tipos de fuente delegan al job más cercano por semántica
    SourceType.PMGE_PROJECTS: JobType.INSTITUTIONAL_PLAN_ANALYSIS,
    SourceType.TECHNOLOGY_AGENDA: JobType.INSTITUTIONAL_PLAN_ANALYSIS,
    SourceType.SUPPORT_DOCUMENT: JobType.DOCUMENT_ANALYSIS,
}

VALID_STATUS_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.UPLOADED: {DocumentStatus.PREPARING, DocumentStatus.FAILED},
    DocumentStatus.PREPARING: {DocumentStatus.PREPARED, DocumentStatus.FAILED},
    DocumentStatus.PREPARED: {DocumentStatus.ANALYZING, DocumentStatus.FAILED},
    DocumentStatus.ANALYZING: {DocumentStatus.VALIDATING, DocumentStatus.FAILED},
    DocumentStatus.VALIDATING: {
        DocumentStatus.READY_TO_PERSIST,
        DocumentStatus.FAILED,
    },
    DocumentStatus.READY_TO_PERSIST: {
        DocumentStatus.PROCESSED,
        DocumentStatus.FAILED,
    },
    DocumentStatus.PROCESSED: set(),
    DocumentStatus.FAILED: set(),
}


@dataclass(frozen=True)
class DocumentRegistration:
    document: Document
    job: ProcessingJob | None
    is_duplicate: bool


class DocumentService:
    """Coordina registro, deduplicacion y estados sin analizar contenido."""

    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def register_document(
        self,
        *,
        file_name: str,
        file_type: str,
        source_type: SourceType,
        content: bytes,
        storage_path: str | None = None,
        document_date: date | None = None,
        replaces_id: str | None = None,
        document_id: str | None = None,
        provider: str | None = None,
    ) -> DocumentRegistration:
        file_hash = self.calculate_sha256(content)
        existing = self._repository.find_document_by_hash(file_hash)
        if existing is not None:
            return DocumentRegistration(document=existing, job=None, is_duplicate=True)

        now = datetime.now(UTC)
        document = Document(
            id=document_id or str(uuid4()),
            file_name=file_name,
            file_type=file_type,
            source_type=source_type,
            file_hash=file_hash,
            storage_path=storage_path,
            document_date=document_date,
            status=DocumentStatus.UPLOADED,
            version=1,
            replaces_id=replaces_id,
            created_at=now,
            updated_at=now,
            provider=provider,
        )
        saved_document = self._repository.save_document(document)
        job = self._new_job(
            document_id=saved_document.id,
            job_type=JobType.DOCUMENT_PREPARATION,
            created_at=now,
        )
        saved_job = self._repository.create_job(job)
        return DocumentRegistration(
            document=saved_document,
            job=saved_job,
            is_duplicate=False,
        )

    def transition_document_status(
        self, document_id: str, next_status: DocumentStatus
    ) -> Document:
        document = self._repository.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")

        allowed = VALID_STATUS_TRANSITIONS[document.status]
        if next_status not in allowed:
            raise InvalidDocumentStatusTransition(
                f"No se permite cambiar documento {document_id} "
                f"de {document.status.value} a {next_status.value}."
            )
        return self._repository.update_document_status(document_id, next_status)

    def create_analysis_job(
        self,
        document_id: str,
        *,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
    ) -> ProcessingJob:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.PREPARED:
            raise InvalidProcessingJobSequence(
                "El analisis solo puede crearse cuando el documento esta prepared."
            )
        return self._create_unique_job(
            document_id=document_id,
            job_type=ANALYSIS_JOB_BY_SOURCE_TYPE[document.source_type],
            prompt_id=prompt_id,
            prompt_version=prompt_version,
        )

    def create_evidence_validation_job(self, document_id: str) -> ProcessingJob:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.VALIDATING:
            raise InvalidProcessingJobSequence(
                "La validacion de evidencia requiere un documento en validating."
            )
        analysis_job_type = ANALYSIS_JOB_BY_SOURCE_TYPE[document.source_type]
        if not self._has_completed_job(document_id, analysis_job_type):
            raise InvalidProcessingJobSequence(
                "La validacion de evidencia requiere analisis completado."
            )
        return self._create_unique_job(
            document_id=document_id,
            job_type=JobType.EVIDENCE_VALIDATION,
        )

    def create_result_persistence_job(self, document_id: str) -> ProcessingJob:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.READY_TO_PERSIST:
            raise InvalidProcessingJobSequence(
                "La persistencia requiere un documento en ready_to_persist."
            )
        if not self._has_completed_job(document_id, JobType.EVIDENCE_VALIDATION):
            raise InvalidProcessingJobSequence(
                "La persistencia requiere validacion de evidencia completada."
            )
        return self._create_unique_job(
            document_id=document_id,
            job_type=JobType.RESULT_PERSISTENCE,
        )

    def _require_document(self, document_id: str) -> Document:
        document = self._repository.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"No existe el documento {document_id}.")
        return document

    def _has_completed_job(self, document_id: str, job_type: JobType) -> bool:
        return any(
            job.job_type == job_type and job.status == JobStatus.COMPLETED
            for job in self._repository.list_jobs(document_id)
        )

    def _create_unique_job(
        self,
        *,
        document_id: str,
        job_type: JobType,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
    ) -> ProcessingJob:
        if any(job.job_type == job_type for job in self._repository.list_jobs(document_id)):
            raise DuplicateProcessingJobError(
                f"Ya existe un job {job_type.value} para el documento {document_id}."
            )
        return self._repository.create_job(
            self._new_job(
                document_id=document_id,
                job_type=job_type,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
            )
        )

    def _new_job(
        self,
        *,
        document_id: str,
        job_type: JobType,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
        created_at: datetime | None = None,
    ) -> ProcessingJob:
        return ProcessingJob(
            id=str(uuid4()),
            document_id=document_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            attempts=0,
            error_message=None,
            created_at=created_at or datetime.now(UTC),
            completed_at=None,
        )
