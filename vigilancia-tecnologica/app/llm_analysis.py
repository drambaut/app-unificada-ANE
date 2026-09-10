"""Análisis local de los resultados estructurados extraídos por LLM."""

from __future__ import annotations

import ast
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

# Permite ``python app/llm_analysis.py`` y ``python -m app.llm_analysis``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import FIGURES_DIR, LOGS_DIR, STRUCTURED_DATA_DIR


INPUT_CSV = STRUCTURED_DATA_DIR / "structured_documents.csv"
REPORT_PATH = STRUCTURED_DATA_DIR / "llm_analysis_report.md"

ANALYSES = {
    "tema_principal": {
        "filename": "llm_temas_principales.csv",
        "list": False,
        "label": "tema_principal",
    },
    "tecnologias": {
        "filename": "llm_tecnologias.csv",
        "list": True,
        "label": "tecnologia",
    },
    "bandas_frecuencia": {
        "filename": "llm_bandas_frecuencia.csv",
        "list": True,
        "label": "banda_frecuencia",
    },
    "paises": {
        "filename": "llm_paises.csv",
        "list": True,
        "label": "pais",
    },
    "organizaciones": {
        "filename": "llm_organizaciones.csv",
        "list": True,
        "label": "organizacion",
    },
    "actores": {
        "filename": "llm_actores.csv",
        "list": True,
        "label": "actor",
    },
    "relevancia_agenda_ane": {
        "filename": "llm_relevancia_agenda_ane.csv",
        "list": False,
        "label": "relevancia_agenda_ane",
    },
    "tipo_documento": {
        "filename": "llm_tipo_documento.csv",
        "list": False,
        "label": "tipo_documento",
    },
}

CHARTS = {
    "tema_principal": (
        "llm_top_temas_principales.png",
        "Top de temas principales",
        "Tema principal",
    ),
    "tecnologias": (
        "llm_top_tecnologias.png",
        "Tecnologías más frecuentes",
        "Tecnología",
    ),
    "bandas_frecuencia": (
        "llm_top_bandas_frecuencia.png",
        "Bandas de frecuencia más mencionadas",
        "Banda de frecuencia",
    ),
    "paises": (
        "llm_top_paises.png",
        "Países más mencionados",
        "País",
    ),
    "organizaciones": (
        "llm_top_organizaciones.png",
        "Organizaciones más frecuentes",
        "Organización",
    ),
    "relevancia_agenda_ane": (
        "llm_relevancia_agenda_ane.png",
        "Relevancia para la Agenda ANE",
        "Nivel de relevancia",
    ),
    "tipo_documento": (
        "llm_tipo_documento.png",
        "Tipos de documento",
        "Tipo de documento",
    ),
}

REQUIRED_COLUMNS = {"llm_status", *ANALYSES.keys()}


def _configure_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("llm_analysis")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    handler = logging.FileHandler(
        LOGS_DIR / "llm_analysis.log", mode="w", encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)
    return logger


def parse_list_value(value: Any, logger: logging.Logger | None = None) -> list[str]:
    """Convierte de forma segura JSON o literales Python en listas de texto."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        parsed = list(value)
    else:
        raw = str(value).strip()
        if not raw:
            return []
        parsed = None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            try:
                parsed = ast.literal_eval(raw)
            except (ValueError, SyntaxError) as exc:
                if logger:
                    logger.warning("Lista no interpretable ignorada: %r | %s", raw, exc)
                return []

    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, (list, tuple, set)):
        if logger:
            logger.warning("Valor de lista con tipo no admitido: %r", parsed)
        return []
    return [str(item) for item in parsed if item is not None]


def _clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _canonical_key(value: str) -> str:
    """Clave insensible a mayúsculas sin alterar siglas en la presentación."""
    return _clean_text(value).casefold()


def _frequency_table(values: Iterable[str], label: str) -> pd.DataFrame:
    """Agrupa variantes de capitalización y conserva una etiqueta representativa."""
    variants: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for raw_value in values:
        display = _clean_text(raw_value)
        if not display:
            continue
        key = _canonical_key(display)
        variants[key][display] += 1
        totals[key] += 1

    rows: list[dict[str, Any]] = []
    total_mentions = sum(totals.values())
    for key, count in totals.most_common():
        # Ante empates conserva la variante con más mayúsculas, útil para siglas.
        display = sorted(
            variants[key],
            key=lambda item: (variants[key][item], sum(char.isupper() for char in item)),
            reverse=True,
        )[0]
        rows.append(
            {
                label: display,
                "count": count,
                "percentage": round(count / total_mentions * 100, 2)
                if total_mentions
                else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=[label, "count", "percentage"])


def _values_for_column(
    dataframe: pd.DataFrame,
    column: str,
    is_list: bool,
    logger: logging.Logger,
) -> list[str]:
    if is_list:
        values: list[str] = []
        for value in dataframe[column]:
            values.extend(parse_list_value(value, logger))
        return values
    return [_clean_text(value) for value in dataframe[column]]


def _save_chart(
    table: pd.DataFrame,
    label: str,
    output_path: Path,
    title: str,
    axis_label: str,
    limit: int = 10,
) -> None:
    top = table.head(limit).sort_values("count", ascending=True)
    plt.figure(figsize=(11, max(5, 0.55 * max(len(top), 1))))
    if top.empty:
        plt.text(0.5, 0.5, "Sin datos disponibles", ha="center", va="center")
        plt.axis("off")
    else:
        plt.barh(top[label], top["count"], color="#2878B5")
        plt.xlabel("Número de menciones")
        plt.ylabel(axis_label)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def _markdown_table(table: pd.DataFrame, limit: int | None = None) -> str:
    display = table.head(limit) if limit is not None else table
    if display.empty:
        return "_Sin datos disponibles._"
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for values in display.itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _top_value(table: pd.DataFrame) -> str:
    return str(table.iloc[0, 0]) if not table.empty else "No disponible"


def _write_report(
    documents_analyzed: int,
    tables: dict[str, pd.DataFrame],
) -> None:
    top_technology = _top_value(tables["tecnologias"])
    top_band = _top_value(tables["bandas_frecuencia"])
    top_relevance = _top_value(tables["relevancia_agenda_ane"])
    top_organization = _top_value(tables["organizaciones"])

    content = f"""# Análisis de resultados estructurados por LLM

**Fecha de generación:** {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}

**Documentos analizados:** {documents_analyzed}

Solo se incluyen registros con `llm_status == "ok"`.

## Distribución de relevancia para la Agenda ANE

{_markdown_table(tables['relevancia_agenda_ane'])}

## Top 10 tecnologías

{_markdown_table(tables['tecnologias'], 10)}

## Top 10 bandas de frecuencia

{_markdown_table(tables['bandas_frecuencia'], 10)}

## Top 10 organizaciones

{_markdown_table(tables['organizaciones'], 10)}

## Top 10 países

{_markdown_table(tables['paises'], 10)}

## Top temas principales

{_markdown_table(tables['tema_principal'], 10)}

## Observaciones automáticas

- La tecnología más recurrente es **{top_technology}**.
- La banda de frecuencia más mencionada es **{top_band}**.
- La mayoría de documentos fueron clasificados con relevancia **{top_relevance}**.
- La organización más frecuente es **{top_organization}**.
"""
    REPORT_PATH.write_text(content, encoding="utf-8")


def analyze_llm_results() -> dict:
    """Genera tablas, gráficas y reporte sobre las extracciones LLM válidas."""
    logger = _configure_logging()
    if not INPUT_CSV.is_file():
        message = (
            f"No se encontró {INPUT_CSV}. Ejecute primero la extracción LLM "
            "con 'python app/llm_extract.py'."
        )
        logger.error(message)
        raise FileNotFoundError(message)

    dataframe = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    missing = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing:
        message = "Faltan columnas requeridas: " + ", ".join(sorted(missing))
        logger.error(message)
        raise ValueError(message)

    valid = dataframe.loc[
        dataframe["llm_status"].fillna("").astype(str).str.strip().str.casefold()
        == "ok"
    ].copy()
    logger.info("Registros totales=%d | registros válidos=%d", len(dataframe), len(valid))

    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}

    for column, settings in ANALYSES.items():
        values = _values_for_column(valid, column, settings["list"], logger)
        table = _frequency_table(values, settings["label"])
        table.to_csv(
            STRUCTURED_DATA_DIR / settings["filename"],
            index=False,
            encoding="utf-8-sig",
        )
        tables[column] = table
        logger.info("Tabla %s: %d categorías", column, len(table))

    for column, (filename, title, axis_label) in CHARTS.items():
        _save_chart(
            tables[column],
            ANALYSES[column]["label"],
            FIGURES_DIR / filename,
            title,
            axis_label,
        )

    _write_report(len(valid), tables)
    logger.info("Análisis finalizado. Reporte=%s", REPORT_PATH)

    result = {
        "documents_analyzed": len(valid),
        "input_rows": len(dataframe),
        "report_path": REPORT_PATH,
        "structured_data_dir": STRUCTURED_DATA_DIR,
        "figures_dir": FIGURES_DIR,
        "tables": tables,
    }
    print("\nAnálisis de resultados LLM completado")
    print(f"- Documentos analizados: {len(valid)}")
    print(f"- Reporte: {REPORT_PATH}")
    return result


if __name__ == "__main__":
    analyze_llm_results()
