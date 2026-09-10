from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF

from app.documents.models import DocumentChunk
from app.preparation.base import DocumentPreparer
from app.preparation.errors import DocumentPreparationError


@dataclass(frozen=True)
class OcrConfig:
    """Configuración para OCR."""
    lang: str = "spa"
    dpi: int = 300
    min_chars: int = 20


class OcrPdfPreparer(DocumentPreparer):
    """
    Extrae texto desde PDF usando OCR.

    - Renderiza cada página a imagen usando PyMuPDF.
    - Aplica OCR con pytesseract si está disponible.
    - Genera 1 chunk por página.
    """

    def __init__(self, *, config: OcrConfig | None = None) -> None:
        self._config = config or OcrConfig()

    def prepare(
        self,
        *,
        document_id: str,
        file_name: str,
        content: bytes,
    ) -> List[DocumentChunk]:
        # Lazy imports para que el pipeline no falle al importar el módulo.
        try:
            from PIL import Image  # noqa: F401
        except Exception as exc:
            raise DocumentPreparationError(
                "OCR requiere Pillow (PIL). Instala 'Pillow' para habilitar OCR."
            ) from exc

        try:
            import pytesseract
        except Exception as exc:
            raise DocumentPreparationError(
                "OCR requiere pytesseract. Instala 'pytesseract' para habilitar OCR."
            ) from exc

        try:
            chunks: List[DocumentChunk] = []
            with fitz.open(stream=content, filetype="pdf") as pdf:
                for index, page in enumerate(pdf, start=1):
                    pix = page.get_pixmap(dpi=self._config.dpi, alpha=False)
                    # pix.samples es bytes RGB/CMYK según el documento; el modo exacto lo
                    # dejamos a Pillow al reconstruir la imagen.
                    mode = "RGB" if pix.n < 5 else "CMYK"
                    img = Image.frombytes(
                        mode,
                        (pix.width, pix.height),
                        pix.samples,
                    )
                    text = pytesseract.image_to_string(img, lang=self._config.lang) or ""
                    text = text.strip()

                    # Reutilizamos el mismo hashing que para chunks normales.
                    cleaned_text = _clean_chunk_text_safely(text)
                    content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

                    chunks.append(
                        DocumentChunk(
                            id=_new_chunk_id(),
                            document_id=document_id,
                            content=cleaned_text,
                            page_number=index,
                            section_title=None,
                            sheet_name=None,
                            row_reference=None,
                            content_hash=content_hash,
                            position=index,
                        )
                    )

            total_text = "".join(chunk.content for chunk in chunks).strip()
            if len(total_text) < self._config.min_chars:
                raise DocumentPreparationError(
                    f"OCR no produjo suficiente texto para {file_name}. "
                    f"min_chars={self._config.min_chars}, total_chars={len(total_text)}"
                )
            return chunks
        except DocumentPreparationError:
            raise
        except Exception as exc:
            raise DocumentPreparationError(
                f"No se pudo ejecutar OCR para el PDF {file_name}: {type(exc).__name__}: {exc}"
            ) from exc


def _new_chunk_id() -> str:
    # Mantiene el contrato de id como string. Evitamos uuid4 aquí para reducir imports.
    import uuid

    return str(uuid.uuid4())


def _clean_chunk_text_safely(text: str) -> str:
    # Reutiliza el cleaning existente del proyecto.
    from app.preparation.text_cleaning import clean_chunk_text

    # clean_chunk_text puede asumir texto; dejamos safe fallback.
    try:
        return clean_chunk_text(text)
    except Exception:
        return text
