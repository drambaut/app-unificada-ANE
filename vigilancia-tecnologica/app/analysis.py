"""Diagnóstico y caracterización exploratoria del corpus documental."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

# Permite ``python app/analysis.py`` además de ``python -m app.analysis``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import FIGURES_DIR, STRUCTURED_DATA_DIR


INPUT_CSV = STRUCTURED_DATA_DIR / "document_texts.csv"
REQUIRED_COLUMNS = {
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
}


def _load_corpus(csv_path: Path) -> pd.DataFrame:
    """Carga y normaliza el CSV producido durante la extracción."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo del corpus: {csv_path}. "
            "Ejecute primero la etapa de construcción del dataset."
        )

    dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"El CSV no contiene las columnas requeridas: {missing}")

    text_columns = [
        "document_id",
        "file_name",
        "source_folder",
        "file_path",
        "file_type",
        "sheet_name",
        "text",
        "status",
        "error_message",
    ]
    dataframe[text_columns] = dataframe[text_columns].fillna("").astype(str)
    dataframe["num_chars"] = (
        pd.to_numeric(dataframe["num_chars"], errors="coerce").fillna(0).clip(lower=0)
    )
    return dataframe


def _document_table(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Consolida las hojas de Excel para obtener una fila por archivo físico."""
    if dataframe.empty:
        return pd.DataFrame(
            columns=[
                "file_path",
                "file_name",
                "source_folder",
                "file_type",
                "num_chars",
                "status",
            ]
        )

    def document_status(statuses: pd.Series) -> str:
        values = set(statuses)
        if "ok" in values:
            return "ok"
        if "error" in values:
            return "error"
        if "empty_text" in values:
            return "empty_text"
        return next(iter(values), "unknown")

    return (
        dataframe.groupby("file_path", as_index=False, dropna=False)
        .agg(
            file_name=("file_name", "first"),
            source_folder=("source_folder", "first"),
            file_type=("file_type", "first"),
            num_chars=("num_chars", "sum"),
            status=("status", document_status),
        )
        .sort_values("file_path", kind="stable")
        .reset_index(drop=True)
    )


def _count_table(series: pd.Series, category_name: str) -> pd.DataFrame:
    """Crea una tabla de frecuencias con porcentaje."""
    normalized = series.replace("", "Sin especificar")
    counts = normalized.value_counts(dropna=False)
    total = int(counts.sum())
    result = counts.rename_axis(category_name).reset_index(name="count")
    result["percentage"] = (
        (result["count"] / total * 100).round(2) if total else 0.0
    )
    return result


def _ranking(documents: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    """Devuelve hasta diez documentos válidos ordenados por longitud."""
    valid = documents[(documents["num_chars"] > 0) & (documents["status"] == "ok")]
    return (
        valid.sort_values("num_chars", ascending=ascending, kind="stable")
        .head(10)[
            [
                "file_name",
                "source_folder",
                "file_path",
                "file_type",
                "num_chars",
                "status",
            ]
        ]
        .reset_index(drop=True)
    )


def _save_bar_chart(
    table: pd.DataFrame,
    category_column: str,
    title: str,
    xlabel: str,
    output_path: Path,
    horizontal: bool = False,
) -> None:
    """Guarda una gráfica de barras legible, incluso con muchas categorías."""
    plt.figure(
        figsize=(11, max(5, 0.45 * len(table))) if horizontal else (9, 6)
    )
    if table.empty:
        plt.text(0.5, 0.5, "Sin datos disponibles", ha="center", va="center")
        plt.axis("off")
    elif horizontal:
        ordered = table.sort_values("count", ascending=True)
        plt.barh(ordered[category_column], ordered["count"], color="#2878B5")
        plt.xlabel(xlabel)
        plt.ylabel("Fuente")
    else:
        plt.bar(table[category_column], table["count"], color="#2878B5")
        plt.xlabel(xlabel)
        plt.ylabel("Número de registros")
        plt.xticks(rotation=35, ha="right")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def _save_length_distribution(documents: pd.DataFrame, output_path: Path) -> None:
    valid_lengths = documents.loc[documents["num_chars"] > 0, "num_chars"]
    plt.figure(figsize=(10, 6))
    if valid_lengths.empty:
        plt.text(0.5, 0.5, "Sin textos válidos", ha="center", va="center")
        plt.axis("off")
    else:
        bins = min(30, max(5, int(len(valid_lengths) ** 0.5)))
        plt.hist(valid_lengths, bins=bins, color="#2878B5", edgecolor="white")
        plt.xlabel("Número de caracteres por documento")
        plt.ylabel("Número de documentos")
    plt.title("Distribución de la longitud de los textos")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def _markdown_table(dataframe: pd.DataFrame) -> str:
    """Genera Markdown sin depender del paquete opcional tabulate."""
    if dataframe.empty:
        return "_Sin datos disponibles._"

    display = dataframe.copy()
    headers = [str(column) for column in display.columns]
    rows = []
    for values in display.itertuples(index=False, name=None):
        rows.append([str(value).replace("|", "\\|").replace("\n", " ") for value in values])
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join([header, separator, body])


def _write_report(
    summary: dict,
    source_counts: pd.DataFrame,
    type_counts: pd.DataFrame,
    status_counts: pd.DataFrame,
    report_path: Path,
) -> None:
    longest_name = summary["longest_document"] or "No disponible"
    top_source = summary["top_source"] or "No disponible"
    observations = [
        f"La fuente con mayor número de documentos es **{top_source}**.",
        (
            "El porcentaje de documentos procesados correctamente es "
            f"**{summary['successful_percentage']:.2f}%**."
        ),
        f"Se identificaron **{summary['empty_texts']}** textos vacíos.",
        f"El documento con mayor volumen de texto es **{longest_name}**.",
    ]

    content = f"""# Reporte exploratorio del corpus documental

**Fecha de generación:** {summary['generated_at']}

## Resumen general

- Total de filas de extracción: **{summary['total_rows']}**
- Total de documentos únicos: **{summary['total_documents']}**
- Textos vacíos: **{summary['empty_texts']}**
- Promedio de caracteres por documento: **{summary['average_chars']:.2f}**
- Mediana de caracteres por documento: **{summary['median_chars']:.2f}**
- Documento más largo: **{longest_name}**
- Documento más corto con texto válido: **{summary['shortest_valid_document'] or 'No disponible'}**

Los conteos por fuente y tipo corresponden a archivos únicos. Los estados corresponden a filas de extracción (un PDF o una hoja de Excel).

## Documentos por fuente

{_markdown_table(source_counts)}

## Tipos de archivo

{_markdown_table(type_counts)}

## Estados de procesamiento

{_markdown_table(status_counts)}

## Observaciones automáticas

"""
    content += "\n".join(f"- {observation}" for observation in observations)
    content += "\n"
    report_path.write_text(content, encoding="utf-8")


def analyze_corpus() -> dict:
    """Genera estadísticas, tablas, gráficas y un reporte Markdown del corpus."""
    dataframe = _load_corpus(INPUT_CSV)
    documents = _document_table(dataframe)
    valid_documents = documents[
        (documents["num_chars"] > 0) & (documents["status"] == "ok")
    ]

    source_counts = _count_table(documents["source_folder"], "source_folder")
    type_counts = _count_table(documents["file_type"], "file_type")
    status_counts = _count_table(dataframe["status"], "status")
    longest = _ranking(documents, ascending=False)
    shortest = _ranking(documents, ascending=True)

    empty_texts = int(
        ((dataframe["num_chars"] == 0) | (dataframe["text"].str.strip() == "")).sum()
    )
    successful_documents = int((documents["status"] == "ok").sum())
    total_documents = len(documents)

    summary = {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "total_rows": len(dataframe),
        "total_documents": total_documents,
        "empty_texts": empty_texts,
        "average_chars": float(documents["num_chars"].mean()) if total_documents else 0.0,
        "median_chars": float(documents["num_chars"].median()) if total_documents else 0.0,
        "longest_document": longest.iloc[0]["file_name"] if not longest.empty else "",
        "longest_document_chars": int(longest.iloc[0]["num_chars"]) if not longest.empty else 0,
        "shortest_valid_document": shortest.iloc[0]["file_name"] if not shortest.empty else "",
        "shortest_valid_document_chars": int(shortest.iloc[0]["num_chars"]) if not shortest.empty else 0,
        "top_source": source_counts.iloc[0]["source_folder"] if not source_counts.empty else "",
        "successful_percentage": (
            successful_documents / total_documents * 100 if total_documents else 0.0
        ),
    }

    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    summary_table = pd.DataFrame(
        [
            ("total_rows", summary["total_rows"]),
            ("total_documents", summary["total_documents"]),
            ("empty_texts", summary["empty_texts"]),
            ("average_chars_per_document", round(summary["average_chars"], 2)),
            ("median_chars_per_document", round(summary["median_chars"], 2)),
            ("longest_document", summary["longest_document"]),
            ("longest_document_chars", summary["longest_document_chars"]),
            ("shortest_valid_document", summary["shortest_valid_document"]),
            ("shortest_valid_document_chars", summary["shortest_valid_document_chars"]),
        ],
        columns=["metric", "value"],
    )

    output_tables = {
        "corpus_summary.csv": summary_table,
        "source_folder_counts.csv": source_counts,
        "file_type_counts.csv": type_counts,
        "status_counts.csv": status_counts,
        "top_longest_documents.csv": longest,
        "top_shortest_documents.csv": shortest,
    }
    for filename, table in output_tables.items():
        table.to_csv(STRUCTURED_DATA_DIR / filename, index=False, encoding="utf-8-sig")

    _save_bar_chart(
        source_counts,
        "source_folder",
        "Documentos por fuente",
        "Número de documentos",
        FIGURES_DIR / "documentos_por_fuente.png",
        horizontal=True,
    )
    _save_bar_chart(
        type_counts,
        "file_type",
        "Tipos de archivo del corpus",
        "Tipo de archivo",
        FIGURES_DIR / "tipos_de_archivo.png",
    )
    _save_bar_chart(
        status_counts,
        "status",
        "Estados del procesamiento documental",
        "Estado",
        FIGURES_DIR / "status_documentos.png",
    )
    _save_length_distribution(
        valid_documents, FIGURES_DIR / "distribucion_longitud_textos.png"
    )

    report_path = STRUCTURED_DATA_DIR / "corpus_report.md"
    _write_report(summary, source_counts, type_counts, status_counts, report_path)

    result = {
        **summary,
        "report_path": report_path,
        "structured_data_dir": STRUCTURED_DATA_DIR,
        "figures_dir": FIGURES_DIR,
    }

    print("\nDiagnóstico del corpus completado")
    print(f"- Filas analizadas: {summary['total_rows']}")
    print(f"- Documentos únicos: {summary['total_documents']}")
    print(f"- Textos vacíos: {summary['empty_texts']}")
    print(f"- Reporte: {report_path}")
    return result


if __name__ == "__main__":
    analyze_corpus()
