"""Workflow integral de procesamiento individual de documentos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from app.documents.models import Document, DocumentChunk, ProcessingJob, SourceType
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.evidence.models import EvidenceValidationReport
from app.evidence.service import EvidenceValidationWorkflow
from app.llm.service import ExtractionResult
from app.results.models import PersistenceBundle
from app.results.repository import ResultRepository
from app.results.service import ResultPersistenceService
from app.workflows.document_analysis import DocumentAnalysisWorkflow


class DocumentProcessingWorkflowError(Exception):
    """Fallo controlado del procesamiento individual completo."""

    def __init__(
        self,
        *,
        stage: str,
        original_error: Exception,
        document_id: str | None = None,
    ) -> None:
        self.stage = stage
        self.document_id = document_id
        self.original_error = original_error
        location = f" document_id={document_id}" if document_id else ""
        super().__init__(f"{stage}{location}: {original_error}")


@dataclass(frozen=True)
class DocumentProcessingWorkflowResult:
    document: Document
    chunks: list[DocumentChunk]
    extraction_result: ExtractionResult
    evidence_report: EvidenceValidationReport
    persistence_bundle: PersistenceBundle
    jobs: list[ProcessingJob]
    completed_at: datetime


class DocumentProcessingWorkflow:
    """Une registro, preparacion, analisis, evidencia y persistencia."""

    def __init__(
        self,
        *,
        document_service: DocumentService,
        analysis_workflow: DocumentAnalysisWorkflow,
        evidence_workflow: EvidenceValidationWorkflow,
        persistence_service: ResultPersistenceService,
        document_repository: DocumentRepository,
        result_repository: ResultRepository,
    ) -> None:
        self._document_service = document_service
        self._analysis_workflow = analysis_workflow
        self._evidence_workflow = evidence_workflow
        self._persistence_service = persistence_service
        self._document_repository = document_repository
        self._result_repository = result_repository

    def run(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        source_type: SourceType,
        metadata: Mapping[str, str] | None = None,
    ) -> DocumentProcessingWorkflowResult:
        document_id: str | None = None
        try:
            registration = self._document_service.register_document(
                file_name=file_name,
                file_type=self._file_type(file_name),
                source_type=source_type,
                content=file_bytes,
                storage_path=None,
            )
            document_id = registration.document.id
            if registration.is_duplicate:
                raise ValueError("Documento duplicado por file_hash.")
        except Exception as exc:
            raise DocumentProcessingWorkflowError(
                stage="registration",
                document_id=document_id,
                original_error=exc,
            ) from exc

        try:
            analysis_result = self._analysis_workflow.run(
                document_id,
                file_bytes,
                metadata=dict(metadata or {}),
            )
        except Exception as exc:
            raise DocumentProcessingWorkflowError(
                stage="analysis",
                document_id=document_id,
                original_error=exc,
            ) from exc

        try:
            evidence_result = self._evidence_workflow.run(
                document_id,
                analysis_result.extraction_result.payload,
            )
            if not evidence_result.report.is_valid:
                raise ValueError("La validacion de evidencia no es valida.")
        except Exception as exc:
            raise DocumentProcessingWorkflowError(
                stage="evidence_validation",
                document_id=document_id,
                original_error=exc,
            ) from exc

        try:
            persistence_result = self._persistence_service.persist(
                document_id=document_id,
                extraction_result=analysis_result.extraction_result,
                evidence_report=evidence_result.report,
            )
        except Exception as exc:
            raise DocumentProcessingWorkflowError(
                stage="result_persistence",
                document_id=document_id,
                original_error=exc,
            ) from exc

        return DocumentProcessingWorkflowResult(
            document=persistence_result.document,
            chunks=analysis_result.chunks,
            extraction_result=analysis_result.extraction_result,
            evidence_report=evidence_result.report,
            persistence_bundle=persistence_result.bundle,
            jobs=self._document_repository.list_jobs(document_id),
            completed_at=datetime.now(UTC),
        )

    def _file_type(self, file_name: str) -> str:
        return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
