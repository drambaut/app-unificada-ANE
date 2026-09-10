from io import StringIO
from pathlib import Path

import fitz
import pandas as pd

from src.data_loader import load_excel, save_csv
from src.utils import clean_column_names


def convert_projects_excel_to_csv(input_path: Path, output_path: Path) -> pd.DataFrame:
    df = load_excel(input_path)
    df = df.copy()
    df.columns = clean_column_names(df.columns)
    save_csv(df, output_path)
    return df


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrae texto del PDF usando PyMuPDF.
    No estructura la hoja de ruta. Solo prepara el texto para enviarlo a Gemini.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    try:
        with fitz.open(pdf_path) as doc:
            text = "\n".join(page.get_text("text") for page in doc)
    except Exception as exc:
        raise RuntimeError(f"No fue posible extraer texto del PDF: {exc}") from exc

    if not text.strip():
        raise ValueError("El PDF no produjo texto legible para enviar a Gemini.")
    return text


def clean_llm_csv_response(response_text: str) -> str:
    """
    Limpia respuestas de Gemini que pueden venir con ```csv ... ```.
    Devuelve solo el contenido CSV.
    """
    text = response_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.lower().startswith("csv\n"):
        text = text[4:].strip()

    return text


def csv_text_to_dataframe(csv_text: str) -> pd.DataFrame:
    """
    Convierte texto CSV a DataFrame.
    Lanza un error claro si la respuesta no es CSV valido.
    """
    cleaned_csv = clean_llm_csv_response(csv_text)
    if not cleaned_csv:
        raise ValueError("Gemini devolvio una respuesta vacia; no hay CSV para leer.")

    try:
        df = pd.read_csv(StringIO(cleaned_csv))
    except Exception as exc:
        raise ValueError(f"Gemini devolvio texto que no es CSV valido: {exc}") from exc

    if df.empty:
        raise ValueError("El CSV devuelto por Gemini esta vacio.")
    return df
