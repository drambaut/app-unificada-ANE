"""Pruebas del diagnóstico exploratorio del corpus."""

from pathlib import Path

import pandas as pd
import pytest

import app.analysis as analysis_module


def _sample_corpus() -> pd.DataFrame:
    columns = [
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
    rows = [
        ["1", "uno.pdf", "Fuente A", "Fuente A/uno.pdf", "pdf", "", "abc", 3, "ok", ""],
        ["2", "libro.xlsx", "Fuente B", "Fuente B/libro.xlsx", "xlsx", "A", "abcd", 4, "ok", ""],
        ["3", "libro.xlsx", "Fuente B", "Fuente B/libro.xlsx", "xlsx", "B", "abcdef", 6, "ok", ""],
        ["4", "vacio.pdf", "Fuente A", "Fuente A/vacio.pdf", "pdf", "", "", 0, "empty_text", ""],
    ]
    return pd.DataFrame(rows, columns=columns)


def test_analyze_corpus_creates_all_outputs(tmp_path: Path, monkeypatch) -> None:
    structured_dir = tmp_path / "structured_data"
    figures_dir = tmp_path / "figures"
    structured_dir.mkdir()
    input_csv = structured_dir / "document_texts.csv"
    _sample_corpus().to_csv(input_csv, index=False, encoding="utf-8-sig")

    monkeypatch.setattr(analysis_module, "INPUT_CSV", input_csv)
    monkeypatch.setattr(analysis_module, "STRUCTURED_DATA_DIR", structured_dir)
    monkeypatch.setattr(analysis_module, "FIGURES_DIR", figures_dir)

    result = analysis_module.analyze_corpus()

    assert result["total_rows"] == 4
    assert result["total_documents"] == 3
    assert result["empty_texts"] == 1
    assert result["longest_document"] == "libro.xlsx"

    expected_tables = {
        "corpus_summary.csv",
        "source_folder_counts.csv",
        "file_type_counts.csv",
        "status_counts.csv",
        "top_longest_documents.csv",
        "top_shortest_documents.csv",
        "corpus_report.md",
    }
    expected_figures = {
        "documentos_por_fuente.png",
        "tipos_de_archivo.png",
        "status_documentos.png",
        "distribucion_longitud_textos.png",
    }
    assert expected_tables.issubset(path.name for path in structured_dir.iterdir())
    assert expected_figures.issubset(path.name for path in figures_dir.iterdir())


def test_analyze_corpus_reports_missing_input(tmp_path: Path, monkeypatch) -> None:
    missing_csv = tmp_path / "document_texts.csv"
    monkeypatch.setattr(analysis_module, "INPUT_CSV", missing_csv)

    with pytest.raises(FileNotFoundError, match="Ejecute primero"):
        analysis_module.analyze_corpus()
