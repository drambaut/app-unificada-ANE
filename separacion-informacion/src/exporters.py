"""Generación de archivos Excel y ZIP en memoria a partir de los resultados."""

from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Dict

import pandas as pd

SHEET_NAME = "PARAMET_TEC_SECTORES_ESTA_BASE"


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = SHEET_NAME) -> bytes:
    """Convierte un DataFrame a los bytes de un archivo .xlsx en memoria.

    Se conservan todas las columnas originales y su orden. El índice de
    pandas nunca se exporta. Si `df` está vacío, el archivo se genera
    igualmente con los encabezados originales.
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def build_result_files(dataframes: Dict[str, pd.DataFrame]) -> Dict[str, bytes]:
    """Convierte un diccionario {nombre_archivo: DataFrame} a {nombre_archivo: bytes}."""
    return {name: dataframe_to_excel_bytes(df) for name, df in dataframes.items()}


def build_zip_bytes(files: Dict[str, bytes]) -> bytes:
    """Empaqueta un diccionario {nombre_archivo: bytes} en un ZIP en memoria."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, data in files.items():
            zip_file.writestr(filename, data)
    return buffer.getvalue()
