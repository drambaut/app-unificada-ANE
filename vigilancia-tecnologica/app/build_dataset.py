"""Construye el dataset inicial a partir de documentos PDF y Excel."""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Permite tanto ``python -m app.build_dataset`` como ``python app/build_dataset.py``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, EXTRACTED_TEXT_DIR, LOGS_DIR, STRUCTURED_DATA_DIR
from app.extract_text import extract_text_from_pdf, save_text_file
from app.process_excels import extract_text_from_excel


SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
OUTPUT_COLUMNS = [
    "document_id",
    "file_name",
    "source_folder",
    "file_path",
    "file_type",
    "sheet_name",
    "text",
    "num_chars",
    "status",
    "error_message",
]


def _configure_logging() -> logging.Logger:
    """Configura un log nuevo para cada ejecución del pipeline."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("build_dataset")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    handler = logging.FileHandler(
        LOGS_DIR / "build_dataset.log", mode="w", encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)
    return logger


def _relative_path(file_path: Path) -> Path:
    """Obtiene la ruta relativa al directorio de datos."""
    return file_path.relative_to(DATA_DIR)


def _document_id(relative_path: Path, sheet_name: str = "") -> str:
    """Genera un identificador determinista por documento u hoja."""
    identity = f"{relative_path.as_posix()}::{sheet_name}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _source_folder(relative_path: Path) -> str:
    """Devuelve la carpeta fuente de primer nivel dentro de DATA_DIR."""
    return relative_path.parts[0] if len(relative_path.parts) > 1 else ""


def _base_record(file_path: Path, sheet_name: str = "") -> dict:
    relative_path = _relative_path(file_path)
    return {
        "document_id": _document_id(relative_path, sheet_name),
        "file_name": file_path.name,
        "source_folder": _source_folder(relative_path),
        "file_path": relative_path.as_posix(),
        "file_type": file_path.suffix.lower().lstrip("."),
        "sheet_name": sheet_name,
    }


def _save_result_text(record: dict, logger: logging.Logger) -> None:
    """Guarda incluso los textos vacíos; registra cualquier fallo de escritura."""
    output_path = EXTRACTED_TEXT_DIR / f"{record['document_id']}.txt"
    try:
        save_text_file(record["text"], output_path)
    except Exception as exc:
        detail = f"No se pudo guardar el TXT: {type(exc).__name__}: {exc}"
        logger.error("%s | %s", record["file_path"], detail)
        record["status"] = "error"
        record["error_message"] = (
            f"{record['error_message']}; {detail}" if record["error_message"] else detail
        )


def build_dataset() -> pd.DataFrame:
    """Recorre DATA_DIR, extrae textos y guarda el dataset consolidado."""
    logger = _configure_logging()
    logger.info("Inicio del procesamiento. DATA_DIR=%s", DATA_DIR)

    if not DATA_DIR.exists() or not DATA_DIR.is_dir():
        message = f"El directorio de datos no existe o no es un directorio: {DATA_DIR}"
        logger.error(message)
        raise FileNotFoundError(message)

    files = sorted(
        (
            path
            for path in DATA_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )

    records: list[dict] = []
    pdf_count = 0
    excel_count = 0
    error_files: set[str] = set()

    print(f"Total de archivos encontrados: {len(files)}")
    logger.info("Archivos encontrados: %d", len(files))

    for file_path in tqdm(files, desc="Procesando documentos", unit="archivo"):
        suffix = file_path.suffix.lower()
        relative_path = _relative_path(file_path)
        logger.info("Procesando: %s", relative_path.as_posix())

        if suffix == ".pdf":
            pdf_count += 1
            result = extract_text_from_pdf(file_path)
            record = {**_base_record(file_path), **result}
            records.append(record)
            _save_result_text(record, logger)

            if record["status"] == "error":
                error_files.add(record["file_path"])
                logger.error("%s | %s", record["file_path"], record["error_message"])
            elif record["status"] == "empty_text":
                logger.warning("Sin texto extraíble: %s", record["file_path"])
        else:
            excel_count += 1
            for result in extract_text_from_excel(file_path):
                sheet_name = result["sheet_name"]
                record = {**_base_record(file_path, sheet_name), **result}
                records.append(record)
                _save_result_text(record, logger)

                if record["status"] == "error":
                    error_files.add(record["file_path"])
                    logger.error(
                        "%s | hoja=%s | %s",
                        record["file_path"],
                        sheet_name,
                        record["error_message"],
                    )
                elif record["status"] == "empty_text":
                    logger.warning(
                        "Sin texto: %s | hoja=%s", record["file_path"], sheet_name
                    )

    dataframe = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    csv_path = STRUCTURED_DATA_DIR / "document_texts.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(csv_path, index=False, encoding="utf-8-sig")

    logger.info(
        "Fin. PDFs=%d | Excels=%d | Errores=%d | Filas=%d | CSV=%s",
        pdf_count,
        excel_count,
        len(error_files),
        len(dataframe),
        csv_path,
    )

    print("\nResumen del procesamiento")
    print(f"- Total de archivos encontrados: {len(files)}")
    print(f"- PDFs procesados: {pdf_count}")
    print(f"- Excels procesados: {excel_count}")
    print(f"- Errores: {len(error_files)}")
    print(f"- Filas generadas: {len(dataframe)}")
    print(f"- CSV final: {csv_path}")

    return dataframe


if __name__ == "__main__":
    build_dataset()
