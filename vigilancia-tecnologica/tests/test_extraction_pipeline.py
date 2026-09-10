"""Pruebas del pipeline inicial con documentos generados temporalmente."""

from pathlib import Path

import fitz
import pandas as pd

import app.build_dataset as build_module
from app.extract_text import extract_text_from_pdf
from app.process_excels import extract_text_from_excel


def _create_pdf(path: Path, texts: list[str]) -> None:
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_pdf_statuses(tmp_path: Path) -> None:
    text_pdf = tmp_path / "text.pdf"
    empty_pdf = tmp_path / "empty.pdf"
    broken_pdf = tmp_path / "broken.pdf"
    _create_pdf(text_pdf, ["Primera pagina", "Segunda pagina"])
    _create_pdf(empty_pdf, [""])
    broken_pdf.write_bytes(b"esto no es un pdf")

    assert extract_text_from_pdf(text_pdf)["status"] == "ok"
    assert extract_text_from_pdf(empty_pdf)["status"] == "empty_text"
    assert extract_text_from_pdf(broken_pdf)["status"] == "error"


def test_excel_returns_one_result_per_sheet(tmp_path: Path) -> None:
    excel_path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame({"columna": ["valor"]}).to_excel(
            writer, sheet_name="Datos", index=False
        )
        pd.DataFrame({"numero": [1]}).to_excel(
            writer, sheet_name="Numeros", index=False
        )

    results = extract_text_from_excel(excel_path)

    assert [result["sheet_name"] for result in results] == ["Datos", "Numeros"]
    assert all(result["status"] == "ok" for result in results)


def test_build_dataset_end_to_end(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    source_dir = data_dir / "Fuente"
    extracted_dir = tmp_path / "outputs" / "extracted_text"
    structured_dir = tmp_path / "outputs" / "structured_data"
    logs_dir = tmp_path / "outputs" / "logs"
    source_dir.mkdir(parents=True)

    _create_pdf(source_dir / "document.pdf", ["Texto de prueba"])
    with pd.ExcelWriter(source_dir / "book.xlsx") as writer:
        pd.DataFrame({"campo": ["contenido"]}).to_excel(
            writer, sheet_name="Hoja 1", index=False
        )

    monkeypatch.setattr(build_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(build_module, "EXTRACTED_TEXT_DIR", extracted_dir)
    monkeypatch.setattr(build_module, "STRUCTURED_DATA_DIR", structured_dir)
    monkeypatch.setattr(build_module, "LOGS_DIR", logs_dir)

    dataframe = build_module.build_dataset()

    assert len(dataframe) == 2
    assert set(dataframe["file_type"]) == {"pdf", "xlsx"}
    assert set(dataframe["status"]) == {"ok"}
    assert set(dataframe["source_folder"]) == {"Fuente"}
    assert (structured_dir / "document_texts.csv").is_file()
    assert (logs_dir / "build_dataset.log").is_file()
    assert len(list(extracted_dir.glob("*.txt"))) == 2
