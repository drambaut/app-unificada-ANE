"""Workflow de validacion de evidencia."""

from __future__ import annotations

from dataclasses import dataclass

from app.documents.models import (
    Document,
    DocumentStatus,
    JobStatus,
    JobType,
    ProcessingJob,
)
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.evidence.errors import EvidenceValidationWorkflowError
from app.evidence.models import EvidenceValidationReport
from app.evidence.validator import EvidenceValidator


@dataclass(frozen=True)
class EvidenceValidationWorkflowResult:
    document: Document
    report: EvidenceValidationReport
    evidence_validation_job: ProcessingJob
    result_persistence_job: ProcessingJob | None


class EvidenceValidationWorkflow:
    """Valida evidencia y abre la persistencia final cuando procede."""

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        validator: EvidenceValidator,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._document_service = DocumentService(repository)

    def run(self, document_id: str, payload: dict) -> EvidenceValidationWorkflowResult:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.VALIDATING:
            raise EvidenceValidationWorkflowError(
                f"El documento debe estar validating; estado actual {document.status.value}."
            )
        job = self._find_queued_validation_job(document_id)
        self._repository.update_job_status(job.id, JobStatus.RUNNING)

        chunks = self._repository.list_chunks(document_id)
        report = self._validator.validate(document, chunks, payload)
        if report.is_valid:
            completed_job = self._repository.update_job_status(
                job.id, JobStatus.COMPLETED
            )
            self._document_service.transition_document_status(
                document_id, DocumentStatus.READY_TO_PERSIST
            )
            persistence_job = self._document_service.create_result_persistence_job(
                document_id
            )
            current_document = self._require_document(document_id)
            return EvidenceValidationWorkflowResult(
                document=current_document,
                report=report,
                evidence_validation_job=completed_job,
                result_persistence_job=persistence_job,
            )

        message = self._summarize(report)
        failed_job = self._repository.update_job_status(
            job.id, JobStatus.FAILED, error_message=message
        )
        self._repository.update_document_status(document_id, DocumentStatus.FAILED)
        return EvidenceValidationWorkflowResult(
            document=self._require_document(document_id),
            report=report,
            evidence_validation_job=failed_job,
            result_persistence_job=None,
        )

    def _require_document(self, document_id: str) -> Document:
        document = self._repository.get_document(document_id)
        if document is None:
            raise EvidenceValidationWorkflowError(f"No existe el documento {document_id}.")
        return document

    def _find_queued_validation_job(self, document_id: str) -> ProcessingJob:
        for job in self._repository.list_jobs(document_id):
            if (
                job.job_type == JobType.EVIDENCE_VALIDATION
                and job.status == JobStatus.QUEUED
            ):
                return job
        raise EvidenceValidationWorkflowError(
            "No existe job EVIDENCE_VALIDATION en estado queued."
        )

    def _summarize(self, report: EvidenceValidationReport) -> str:
        invalid = [item for item in report.items if item.status.value != "verified"]
        return "; ".join(
            f"{item.evidence_id}: {item.status.value}" for item in invalid[:5]
        )
