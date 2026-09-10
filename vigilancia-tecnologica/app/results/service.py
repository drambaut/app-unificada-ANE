"""Servicio de persistencia abstracta de resultados."""

from __future__ import annotations

from dataclasses import dataclass

from app.documents.models import Document, DocumentStatus, JobStatus, JobType, ProcessingJob
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.evidence.models import EvidenceValidationReport
from app.llm.service import ExtractionResult
from app.results.errors import ResultPersistenceWorkflowError
from app.results.models import PersistenceBundle
from app.results.normalizer import ResultNormalizer
from app.results.repository import ResultRepository


@dataclass(frozen=True)
class ResultPersistenceWorkflowResult:
    document: Document
    bundle: PersistenceBundle
    result_persistence_job: ProcessingJob


class ResultPersistenceService:
    """Normaliza, guarda atomicamente y cierra el flujo individual."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        result_repository: ResultRepository,
        normalizer: ResultNormalizer,
    ) -> None:
        self._document_repository = document_repository
        self._result_repository = result_repository
        self._normalizer = normalizer
        self._document_service = DocumentService(document_repository)

    def persist(
        self,
        *,
        document_id: str,
        extraction_result: ExtractionResult,
        evidence_report: EvidenceValidationReport,
    ) -> ResultPersistenceWorkflowResult:
        document = self._require_document(document_id)
        if document.status != DocumentStatus.READY_TO_PERSIST:
            raise ResultPersistenceWorkflowError(
                f"El documento debe estar ready_to_persist; estado actual {document.status.value}."
            )
        job = self._find_queued_persistence_job(document_id)
        self._document_repository.update_job_status(job.id, JobStatus.RUNNING)

        try:
            bundle = self._normalizer.normalize(
                document, extraction_result, evidence_report
            )
            saved = self._result_repository.save_bundle(bundle)
            completed_job = self._document_repository.update_job_status(
                job.id, JobStatus.COMPLETED
            )
            processed = self._document_service.transition_document_status(
                document_id, DocumentStatus.PROCESSED
            )
            return ResultPersistenceWorkflowResult(
                document=processed,
                bundle=saved,
                result_persistence_job=completed_job,
            )
        except Exception as exc:
            message = str(exc)
            self._document_repository.update_job_status(
                job.id, JobStatus.FAILED, error_message=message
            )
            self._document_repository.update_document_status(
                document_id, DocumentStatus.FAILED
            )
            raise ResultPersistenceWorkflowError(message) from exc

    def _require_document(self, document_id: str) -> Document:
        document = self._document_repository.get_document(document_id)
        if document is None:
            raise ResultPersistenceWorkflowError(f"No existe el documento {document_id}.")
        return document

    def _find_queued_persistence_job(self, document_id: str) -> ProcessingJob:
        for job in self._document_repository.list_jobs(document_id):
            if (
                job.job_type == JobType.RESULT_PERSISTENCE
                and job.status == JobStatus.QUEUED
            ):
                return job
        raise ResultPersistenceWorkflowError(
            "No existe job RESULT_PERSISTENCE en estado queued."
        )
