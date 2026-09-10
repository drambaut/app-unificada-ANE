"""Utilidades para extraer y guardar texto de archivos PDF."""

from pathlib import Path

import fitz


def extract_text_from_pdf(pdf_path: Path) -> dict:
    """Extrae el texto de un PDF página por página sin usar OCR.

    La función siempre devuelve un resultado y captura los errores propios del
    archivo para que un documento defectuoso no interrumpa el pipeline.
    """
    pdf_path = Path(pdf_path)

    try:
        page_texts: list[str] = []
        with fitz.open(pdf_path) as document:
            for page in document:
                page_texts.append(page.get_text("text"))

        text = "\n".join(page_texts).strip()
        return {
            "text": text,
            "num_chars": len(text),
            "status": "ok" if text else "empty_text",
            "error_message": "",
        }
    except Exception as exc:  # PyMuPDF puede lanzar distintos tipos de error.
        return {
            "text": "",
            "num_chars": 0,
            "status": "error",
            "error_message": f"{type(exc).__name__}: {exc}",
        }


def save_text_file(text: str, output_path: Path) -> None:
    """Guarda texto UTF-8 y crea el directorio de destino si hace falta."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
