"""Workflow completo para documentos cargados manualmente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from app.documents.models import Document, DocumentChunk, ProcessingJob, SourceType
from app.documents.repository import DocumentRepository
from app.evidence.models import EvidenceValidationReport
from app.evidence.service import EvidenceValidationWorkflow
from app.llm.service import ExtractionResult
from app.results.models import PersistenceBundle
from app.results.service import ResultPersistenceService
from app.workflows.document_analysis import DocumentAnalysisWorkflow
from app.workflows.manual_upload import (
    ManualDocumentUploadResult,
    ManualDocumentUploadService,
)


class ManualDocumentProcessingWorkflowError(Exception):
    """Fallo controlado del flujo manual completo."""

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
class ManualDocumentProcessingResult:
    upload: ManualDocumentUploadResult
    document: Document
    chunks: list[DocumentChunk]
    extraction_result: ExtractionResult
    evidence_report: EvidenceValidationReport
    persistence_bundle: PersistenceBundle
    jobs: list[ProcessingJob]
    completed_at: datetime


class ManualDocumentProcessingWorkflow:
    """Orquesta carga manual y procesamiento individual completo."""

    def __init__(
        self,
        *,
        upload_service: ManualDocumentUploadService,
        analysis_workflow: DocumentAnalysisWorkflow,
        evidence_workflow: EvidenceValidationWorkflow,
        persistence_service: ResultPersistenceService,
        document_repository: DocumentRepository,
    ) -> None:
        self._upload_service = upload_service
        self._analysis_workflow = analysis_workflow
        self._evidence_workflow = evidence_workflow
        self._persistence_service = persistence_service
        self._document_repository = document_repository

    def run(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        source_type: SourceType,
        metadata: Mapping[str, str] | None = None,
        content_type: str | None = None,
        reuse_uploaded_duplicate: bool = False,
    ) -> ManualDocumentProcessingResult:
        document_id: str | None = None
        try:
            upload = self._upload_service.upload(
                file_name=file_name,
                content=file_bytes,
                source_type=source_type,
                content_type=content_type,
                metadata=metadata,
                reuse_uploaded_duplicate=reuse_uploaded_duplicate,
            )
            document_id = upload.document.id
            if upload.is_duplicate:
                raise ValueError("Documento duplicado por file_hash.")
        except Exception as exc:
            raise ManualDocumentProcessingWorkflowError(
                stage="upload",
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
            raise ManualDocumentProcessingWorkflowError(
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
                raise ValueError(_summarize_invalid_evidence(evidence_result.report))
        except Exception as exc:
            raise ManualDocumentProcessingWorkflowError(
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
            raise ManualDocumentProcessingWorkflowError(
                stage="result_persistence",
                document_id=document_id,
                original_error=exc,
            ) from exc

        return ManualDocumentProcessingResult(
            upload=upload,
            document=persistence_result.document,
            chunks=analysis_result.chunks,
            extraction_result=analysis_result.extraction_result,
            evidence_report=evidence_result.report,
            persistence_bundle=persistence_result.bundle,
            jobs=self._document_repository.list_jobs(document_id),
            completed_at=datetime.now(UTC),
        )


def _summarize_invalid_evidence(report: EvidenceValidationReport) -> str:
    invalid_items = [item for item in report.items if item.status.value != "verified"]
    details = []
    for item in invalid_items[:5]:
        location = (
            f"page={item.page_number}"
            if item.page_number is not None
            else f"sheet={item.sheet_name} row={item.row_reference}"
            if item.sheet_name or item.row_reference
            else "sin ubicacion"
        )
        details.append(
            f"{item.evidence_id}: {item.status.value} ({location}; {item.message})"
        )
    suffix = ""
    if len(invalid_items) > 5:
        suffix = f"; +{len(invalid_items) - 5} mas"
    return "La validacion de evidencia no es valida: " + "; ".join(details) + suffix
