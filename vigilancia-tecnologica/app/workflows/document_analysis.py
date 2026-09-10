"""Workflow de analisis individual de documentos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    ProcessingJob,
    SourceType,
)
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.llm.input_builder import build_excel_input, build_pdf_input
from app.llm.service import ExtractionResult, StructuredExtractionService
from app.preparation.service import DocumentPreparationService
from app.workflows.errors import WorkflowError


PROMPT_BY_SOURCE_TYPE: dict[SourceType, tuple[str, str]] = {
    SourceType.SURVEILLANCE: ("document_extraction", "v1"),
    SourceType.INSTITUTIONAL_PLAN: ("institutional_plan_extraction", "v1"),
    SourceType.POLICY_MATRIX: ("policy_matrix_extraction", "v1"),
}


@dataclass(frozen=True)
class DocumentAnalysisWorkflowResult:
    document: Document
    chunks: list[DocumentChunk]
    extraction_result: ExtractionResult
    preparation_job: ProcessingJob
    analysis_job: ProcessingJob
    evidence_validation_job: ProcessingJob


class DocumentAnalysisWorkflow:
    """Conecta preparacion, LLM estructurado y jobs sin persistencia final."""

    def __init__(
        self,
        *,
        document_service: DocumentService,
        preparation_service: DocumentPreparationService,
        extraction_service: StructuredExtractionService,
        repository: DocumentRepository,
    ) -> None:
        self._document_service = document_service
        self._preparation_service = preparation_service
        self._extraction_service = extraction_service
        self._repository = repository

    def run(
        self,
        document_id: str,
        file_bytes: bytes,
        metadata: Mapping[str, str] | None = None,
    ) -> DocumentAnalysisWorkflowResult:
        document = self._get_runnable_document(document_id)
        preparation_job = self._get_preparation_job(document_id)

        try:
            chunks = self._preparation_service.prepare_document(
                document_id=document.id,
                file_name=document.file_name,
                content=file_bytes,
            )
        except Exception as exc:
            raise WorkflowError("preparation", str(exc)) from exc

        try:
            analysis_job = self._document_service.create_analysis_job(
                document.id,
                prompt_id=PROMPT_BY_SOURCE_TYPE[document.source_type][0],
                prompt_version=PROMPT_BY_SOURCE_TYPE[document.source_type][1],
            )
            self._document_service.transition_document_status(
                document.id, DocumentStatus.ANALYZING
            )
            self._repository.update_job_status(analysis_job.id, JobStatus.RUNNING)

            prompt_id, prompt_version = PROMPT_BY_SOURCE_TYPE[document.source_type]
            input_data = self._build_input(
                document=document,
                file_bytes=file_bytes,
                chunks=chunks,
                metadata=metadata or {},
            )
            extraction_result = self._extraction_service.extract(
                prompt_id=prompt_id,
                version=prompt_version,
                input_data=input_data,
            )

            analysis_job = self._repository.update_job_status(
                analysis_job.id, JobStatus.COMPLETED
            )
            self._document_service.transition_document_status(
                document.id, DocumentStatus.VALIDATING
            )
            evidence_validation_job = (
                self._document_service.create_evidence_validation_job(document.id)
            )
            current_document = self._repository.get_document(document.id)
            if current_document is None:
                raise WorkflowError("finalize", f"No existe el documento {document.id}.")
            return DocumentAnalysisWorkflowResult(
                document=current_document,
                chunks=chunks,
                extraction_result=extraction_result,
                preparation_job=self._get_preparation_job(document.id),
                analysis_job=analysis_job,
                evidence_validation_job=evidence_validation_job,
            )
        except WorkflowError:
            raise
        except Exception as exc:
            self._fail_document(document.id, analysis_job if "analysis_job" in locals() else None, str(exc))
            raise WorkflowError("analysis", str(exc)) from exc

    def _get_runnable_document(self, document_id: str) -> Document:
        document = self._repository.get_document(document_id)
        if document is None:
            raise WorkflowError("document_lookup", f"No existe el documento {document_id}.")
        if document.status == DocumentStatus.FAILED:
            raise WorkflowError("precondition", "No se analiza un documento failed.")
        if document.status != DocumentStatus.UPLOADED:
            raise WorkflowError(
                "precondition",
                f"El workflow inicia solo desde uploaded; estado actual {document.status.value}.",
            )
        return document

    def _get_preparation_job(self, document_id: str) -> ProcessingJob:
        for job in self._repository.list_jobs(document_id):
            if job.job_type.value == "document_preparation":
                return job
        raise WorkflowError("preparation", "No existe job DOCUMENT_PREPARATION.")

    def _build_input(
        self,
        *,
        document: Document,
        file_bytes: bytes,
        chunks: list[DocumentChunk],
        metadata: Mapping[str, str],
    ):
        full_metadata = {
            "document_id": document.id,
            "source_type": document.source_type.value,
            **dict(metadata),
        }
        extension = Path(document.file_name).suffix.lower()
        if extension == ".pdf" or document.file_type.lower() == "pdf":
            return build_pdf_input(
                file_name=document.file_name,
                file_bytes=file_bytes,
                metadata=full_metadata,
            )
        return build_excel_input(
            file_name=document.file_name,
            chunks=chunks,
            metadata=full_metadata,
        )

    def _fail_document(
        self, document_id: str, active_job: ProcessingJob | None, message: str
    ) -> None:
        if active_job is not None:
            self._repository.update_job_status(
                active_job.id, JobStatus.FAILED, error_message=message
            )
        self._repository.update_document_status(document_id, DocumentStatus.FAILED)
