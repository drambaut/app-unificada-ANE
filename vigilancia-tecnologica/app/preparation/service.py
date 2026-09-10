"""Servicio de preparacion tecnica con persistencia de chunks."""

from __future__ import annotations

from pathlib import Path

from app.documents.models import DocumentChunk
from app.documents.models import DocumentStatus, JobStatus, JobType
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.preparation.base import DocumentPreparer
from app.preparation.errors import (
    DocumentPreparationError,
    OcrRequiredError,
    PreparationJobNotFoundError,
    UnsupportedDocumentFormatError,
)
from app.preparation.excel import ExcelDocumentPreparer
from app.preparation.ocr import OcrPdfPreparer
from app.preparation.pdf import PdfDocumentPreparer


class DocumentPreparationService:
    """Ejecuta la preparacion tecnica sin analisis semantico."""

    def __init__(
        self,
        repository: DocumentRepository,
        preparers: dict[str, DocumentPreparer] | None = None,
    ) -> None:
        self._repository = repository
        self._document_service = DocumentService(repository)
        self._preparers = preparers or {
            ".pdf": PdfDocumentPreparer(),
            ".xlsx": ExcelDocumentPreparer(),
            ".xls": ExcelDocumentPreparer(),
        }

    def prepare_document(
        self,
        *,
        document_id: str,
        file_name: str,
        content: bytes,
    ) -> list[DocumentChunk]:
        job = self._find_preparation_job(document_id)

        try:
            extension = Path(file_name).suffix.lower()
            preparer = self._select_preparer(file_name)

            self._document_service.transition_document_status(
                document_id, DocumentStatus.PREPARING
            )
            self._repository.update_job_status(job.id, JobStatus.RUNNING)

            try:
                chunks = preparer.prepare(
                    document_id=document_id,
                    file_name=file_name,
                    content=content,
                )
            except OcrRequiredError:
                # Fallback OCR para PDFs sin texto suficiente.
                if extension != ".pdf":
                    raise
                ocr_preparer = OcrPdfPreparer()
                chunks = ocr_preparer.prepare(
                    document_id=document_id,
                    file_name=file_name,
                    content=content,
                )
            for chunk in chunks:
                self._repository.save_chunk(chunk)
            self._repository.update_job_status(job.id, JobStatus.COMPLETED)
            self._document_service.transition_document_status(
                document_id, DocumentStatus.PREPARED
            )
            return chunks
        except Exception as exc:
            message = str(exc)
            self._repository.update_job_status(
                job.id, JobStatus.FAILED, error_message=message
            )
            self._repository.update_document_status(document_id, DocumentStatus.FAILED)
            if isinstance(exc, DocumentPreparationError):
                raise
            raise DocumentPreparationError(message) from exc

    def _select_preparer(self, file_name: str) -> DocumentPreparer:
        extension = Path(file_name).suffix.lower()
        preparer = self._preparers.get(extension)
        if preparer is None:
            raise UnsupportedDocumentFormatError(
                f"Formato no soportado para preparacion: {extension or file_name}."
            )
        return preparer

    def _find_preparation_job(self, document_id: str):
        for job in self._repository.list_jobs(document_id):
            if job.job_type == JobType.DOCUMENT_PREPARATION:
                return job
        raise PreparationJobNotFoundError(
            f"El documento {document_id} no tiene job DOCUMENT_PREPARATION."
        )
