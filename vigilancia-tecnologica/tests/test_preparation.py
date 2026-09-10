"""Pruebas de preparacion tecnica de documentos."""

from __future__ import annotations

import struct
from io import BytesIO

import fitz
import pandas as pd
import pytest

import app.preparation.excel as excel_module
import app.preparation.pdf as pdf_module
from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import (
    DocumentStatus,
    JobStatus,
    JobType,
    SourceType,
)
from app.documents.service import DocumentService
from app.preparation.errors import (
    DocumentPreparationError,
    OcrRequiredError,
    UnsupportedDocumentFormatError,
)
from app.preparation.excel import ExcelDocumentPreparer
from app.preparation.pdf import PdfDocumentPreparer
from app.preparation.service import DocumentPreparationService
from app.preparation.text_cleaning import clean_chunk_text


def make_pdf_bytes(texts: list[str]) -> bytes:
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    output = document.tobytes()
    document.close()
    return output


def make_excel_bytes() -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(
            {"policy": ["A", "B"], "owner": ["Area 1", "Area 2"]}
        ).to_excel(writer, sheet_name="Policies", index=False)
        pd.DataFrame({"commitment": ["C"]}).to_excel(
            writer, sheet_name="Commitments", index=False
        )
    return output.getvalue()


def make_xls_bytes() -> bytes:
    def record(opcode: int, data: bytes) -> bytes:
        return struct.pack("<HH", opcode, len(data)) + data

    return b"".join(
        [
            record(0x0009, struct.pack("<HH", 0x0002, 0x0010)),
            record(0x0004, struct.pack("<HHHB", 0, 0, 0, 5) + b"valor"),
            record(0x000A, b""),
        ]
    )


def register_document(
    *,
    file_type: str = "pdf",
    source_type: SourceType = SourceType.SURVEILLANCE,
    content: bytes = b"contenido",
) -> tuple[DocumentService, InMemoryDocumentRepository, str, str]:
    repository = InMemoryDocumentRepository()
    document_service = DocumentService(repository)
    registration = document_service.register_document(
        file_name=f"documento.{file_type}",
        file_type=file_type,
        source_type=source_type,
        content=content,
        storage_path=f"storage/documento.{file_type}",
    )
    assert registration.job is not None
    return document_service, repository, registration.document.id, registration.job.id


def test_pdf_preparer_extracts_multiple_pages_with_page_number() -> None:
    content = make_pdf_bytes(
        [
            "Primera pagina con texto suficiente para preparar.",
            "Segunda pagina con texto suficiente para preparar.",
        ]
    )

    chunks = PdfDocumentPreparer().prepare(
        document_id="doc-1", file_name="documento.pdf", content=content
    )

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert [chunk.position for chunk in chunks] == [1, 2]
    assert all(chunk.sheet_name is None for chunk in chunks)


def test_clean_chunk_text_removes_postgres_incompatible_nul() -> None:
    assert clean_chunk_text("antes\0despues") == "antesdespues"


def test_pdf_preparer_preserves_empty_pages_when_document_has_text() -> None:
    content = make_pdf_bytes(
        [
            "Pagina inicial con texto suficiente para que el PDF no requiera OCR.",
            "",
        ]
    )

    chunks = PdfDocumentPreparer().prepare(
        document_id="doc-1", file_name="documento.pdf", content=content
    )

    assert len(chunks) == 2
    assert chunks[1].page_number == 2
    assert chunks[1].content.strip() == ""


def test_pdf_without_text_reports_possible_ocr_need() -> None:
    content = make_pdf_bytes(["", ""])

    with pytest.raises(OcrRequiredError, match="OCR"):
        PdfDocumentPreparer().prepare(
            document_id="doc-1", file_name="empty.pdf", content=content
        )


def test_excel_preparer_extracts_multiple_sheets_with_row_references() -> None:
    chunks = ExcelDocumentPreparer().prepare(
        document_id="doc-1",
        file_name="book.xlsx",
        content=make_excel_bytes(),
    )

    assert [chunk.sheet_name for chunk in chunks] == [
        "Policies",
        "Policies",
        "Commitments",
    ]
    assert [chunk.row_reference for chunk in chunks] == ["2", "3", "2"]
    assert [chunk.position for chunk in chunks] == [1, 2, 3]
    assert all(chunk.page_number is None for chunk in chunks)
    assert "policy" in chunks[0].content
    assert "commitment" in chunks[2].content


def test_excel_preparer_supports_real_xls_with_xlrd() -> None:
    chunks = ExcelDocumentPreparer().prepare(
        document_id="doc-1",
        file_name="book.xls",
        content=make_xls_bytes(),
    )

    assert len(chunks) == 1
    assert chunks[0].sheet_name == "Sheet 1"
    assert chunks[0].row_reference == "empty"
    assert "alor" in chunks[0].content


def test_chunk_hashes_are_deterministic() -> None:
    content = make_excel_bytes()
    first = ExcelDocumentPreparer().prepare(
        document_id="doc-1", file_name="book.xlsx", content=content
    )
    second = ExcelDocumentPreparer().prepare(
        document_id="doc-1", file_name="book.xlsx", content=content
    )

    assert [chunk.content_hash for chunk in first] == [
        chunk.content_hash for chunk in second
    ]


def test_preparation_service_rejects_unsupported_extension_and_marks_failed() -> None:
    _document_service, repository, document_id, job_id = register_document(
        file_type="txt"
    )
    service = DocumentPreparationService(repository)

    with pytest.raises(UnsupportedDocumentFormatError):
        service.prepare_document(
            document_id=document_id,
            file_name="documento.txt",
            content=b"texto",
        )

    assert repository.get_document(document_id).status == DocumentStatus.FAILED
    job = repository.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert "Formato no soportado" in job.error_message


def test_preparation_service_transitions_state_and_completes_job() -> None:
    pdf_bytes = make_pdf_bytes(["Texto suficiente para preparar correctamente."])
    _document_service, repository, document_id, job_id = register_document(
        file_type="pdf", content=pdf_bytes
    )
    service = DocumentPreparationService(repository)

    chunks = service.prepare_document(
        document_id=document_id,
        file_name="documento.pdf",
        content=pdf_bytes,
    )

    assert chunks == repository.list_chunks(document_id)
    assert repository.get_document(document_id).status == DocumentStatus.PREPARED
    job = repository.get_job(job_id)
    assert job.job_type == JobType.DOCUMENT_PREPARATION
    assert job.status == JobStatus.COMPLETED


def test_preparation_service_handles_preparer_error_and_marks_failed() -> None:
    class FailingPreparer:
        def prepare(self, *, document_id: str, file_name: str, content: bytes):
            raise DocumentPreparationError("fallo controlado")

    _document_service, repository, document_id, job_id = register_document()
    service = DocumentPreparationService(repository, preparers={".pdf": FailingPreparer()})

    with pytest.raises(DocumentPreparationError, match="fallo controlado"):
        service.prepare_document(
            document_id=document_id,
            file_name="documento.pdf",
            content=b"pdf",
        )

    assert repository.get_document(document_id).status == DocumentStatus.FAILED
    job = repository.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error_message == "fallo controlado"


def test_preparation_does_not_call_gemini() -> None:
    pdf_source = pdf_module.__loader__.get_source(pdf_module.__name__)
    excel_source = excel_module.__loader__.get_source(excel_module.__name__)

    assert "google.genai" not in pdf_source
    assert "google.genai" not in excel_source
    assert "Gemini" not in pdf_source
    assert "Gemini" not in excel_source
