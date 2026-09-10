"""Pruebas del análisis local de resultados estructurados por LLM."""

from pathlib import Path

import pandas as pd
import pytest

import app.llm_analysis as analysis_module


def _sample_data() -> pd.DataFrame:
    base = {
        "temas_secundarios": "[]",
        "actores": "[]",
        "llm_error": "",
    }
    return pd.DataFrame(
        [
            {
                **base,
                "document_id": "1",
                "tema_principal": "Gestión del espectro",
                "tecnologias": '["5G", "NTN"]',
                "bandas_frecuencia": "['3.5 GHz']",
                "paises": '["Colombia"]',
                "organizaciones": '["CRC"]',
                "relevancia_agenda_ane": "Alta",
                "tipo_documento": "Reporte",
                "llm_status": "ok",
            },
            {
                **base,
                "document_id": "2",
                "tema_principal": "gestión del espectro",
                "tecnologias": "['5g', '6G']",
                "bandas_frecuencia": '["3.5 GHz"]',
                "paises": '["colombia"]',
                "organizaciones": '["crc", "GSMA"]',
                "relevancia_agenda_ane": "Alta",
                "tipo_documento": "reporte",
                "llm_status": "OK",
            },
            {
                **base,
                "document_id": "3",
                "tema_principal": "No contar",
                "tecnologias": '["4G"]',
                "bandas_frecuencia": "[]",
                "paises": "[]",
                "organizaciones": "[]",
                "relevancia_agenda_ane": "Baja",
                "tipo_documento": "Nota",
                "llm_status": "error",
            },
        ]
    )


def _patch_paths(tmp_path: Path, monkeypatch) -> None:
    structured = tmp_path / "structured"
    figures = tmp_path / "figures"
    logs = tmp_path / "logs"
    structured.mkdir()
    input_csv = structured / "structured_documents.csv"
    _sample_data().to_csv(input_csv, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(analysis_module, "INPUT_CSV", input_csv)
    monkeypatch.setattr(analysis_module, "REPORT_PATH", structured / "report.md")
    monkeypatch.setattr(analysis_module, "STRUCTURED_DATA_DIR", structured)
    monkeypatch.setattr(analysis_module, "FIGURES_DIR", figures)
    monkeypatch.setattr(analysis_module, "LOGS_DIR", logs)


def test_parse_list_value_supports_json_and_python_literals() -> None:
    assert analysis_module.parse_list_value('["5G", "6G"]') == ["5G", "6G"]
    assert analysis_module.parse_list_value("['NTN', 'IoT']") == ["NTN", "IoT"]
    assert analysis_module.parse_list_value("") == []
    assert analysis_module.parse_list_value("texto inválido") == []


def test_analyze_llm_results_creates_expected_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    _patch_paths(tmp_path, monkeypatch)

    result = analysis_module.analyze_llm_results()

    assert result["documents_analyzed"] == 2
    technologies = result["tables"]["tecnologias"]
    assert technologies.iloc[0]["tecnologia"] == "5G"
    assert technologies.iloc[0]["count"] == 2
    organizations = result["tables"]["organizaciones"]
    assert organizations.iloc[0]["organizacion"] == "CRC"
    assert organizations.iloc[0]["count"] == 2

    expected_csvs = {settings["filename"] for settings in analysis_module.ANALYSES.values()}
    expected_charts = {settings[0] for settings in analysis_module.CHARTS.values()}
    assert expected_csvs.issubset(path.name for path in result["structured_data_dir"].iterdir())
    assert expected_charts.issubset(path.name for path in result["figures_dir"].iterdir())
    assert result["report_path"].is_file()


def test_missing_structured_documents_has_clear_error(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(analysis_module, "INPUT_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(analysis_module, "LOGS_DIR", tmp_path / "logs")

    with pytest.raises(FileNotFoundError, match="llm_extract.py"):
        analysis_module.analyze_llm_results()
