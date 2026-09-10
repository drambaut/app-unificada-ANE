"""Preparacion tecnica de documentos PDF."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import fitz

from app.documents.models import DocumentChunk
from app.preparation.errors import DocumentPreparationError, OcrRequiredError
from app.preparation.text_cleaning import clean_chunk_text


class PdfDocumentPreparer:
    """Extrae texto por pagina desde bytes PDF sin OCR ni analisis semantico."""

    def __init__(self, *, min_text_chars: int = 20) -> None:
        self._min_text_chars = min_text_chars

    def prepare(
        self,
        *,
        document_id: str,
        file_name: str,
        content: bytes,
    ) -> list[DocumentChunk]:
        try:
            chunks: list[DocumentChunk] = []
            with fitz.open(stream=content, filetype="pdf") as document:
                for index, page in enumerate(document, start=1):
                    text = clean_chunk_text(page.get_text("text"))
                    chunks.append(
                        DocumentChunk(
                            id=str(uuid4()),
                            document_id=document_id,
                            content=text,
                            page_number=index,
                            section_title=None,
                            sheet_name=None,
                            row_reference=None,
                            content_hash=hashlib.sha256(
                                text.encode("utf-8")
                            ).hexdigest(),
                            position=index,
                        )
                    )
        except Exception as exc:
            raise DocumentPreparationError(
                f"No se pudo preparar el PDF {file_name}: {type(exc).__name__}: {exc}"
            ) from exc

        total_text = "".join(chunk.content for chunk in chunks).strip()
        if len(total_text) < self._min_text_chars:
            pages = [chunk.page_number for chunk in chunks]
            raise OcrRequiredError(
                f"El PDF {file_name} no tiene texto suficiente; posible OCR requerido. "
                f"Paginas revisadas: {pages}."
            )
        return chunks
