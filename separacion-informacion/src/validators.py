"""Validaciones de entrada para los archivos de estaciones base.

Todas las funciones de este módulo levantan `FileValidationError` con un
mensaje comprensible cuando algo no cumple lo esperado. El detalle técnico
(excepción original) se registra con `logging` y nunca se muestra tal cual
al usuario final.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import BinaryIO, Union

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_SHEET = "PARAMET_TEC_SECTORES_ESTA_BASE"

REQUIRED_COLUMNS = [
    "LONGITUD",
    "LATITUD",
    "IDENT_SECT_ESTAC_BASE_POR_TEC",
    "BANDA_FRECUENCIA_OPERAC_SECTOR",
]

VALID_EXTENSIONS = (".xlsx", ".xls")


class FileValidationError(Exception):
    """Error de validación con un mensaje apto para mostrar en la interfaz."""


def validate_extension(filename: str, empresa_label: str) -> None:
    """Verifica que el nombre de archivo tenga una extensión Excel válida."""
    if not filename.lower().endswith(VALID_EXTENSIONS):
        raise FileValidationError(
            f"El archivo cargado para {empresa_label} ('{filename}') no tiene "
            f"una extensión válida. Se esperaba .xlsx o .xls."
        )


def _open_excel_file(file_obj: Union[BinaryIO, BytesIO], filename: str, empresa_label: str) -> pd.ExcelFile:
    """Abre el archivo Excel controlando errores de lectura."""
    try:
        return pd.ExcelFile(file_obj)
    except Exception as exc:
        logger.exception("Error abriendo el archivo %s de %s", filename, empresa_label)
        raise FileValidationError(
            f"No fue posible leer el archivo de {empresa_label} ('{filename}'). "
            f"Verifique que el archivo no esté dañado y que sea un Excel válido."
        ) from exc


def _validate_sheet_present(excel_file: pd.ExcelFile, filename: str, empresa_label: str) -> None:
    """Verifica que la hoja requerida exista en el archivo."""
    if REQUIRED_SHEET not in excel_file.sheet_names:
        raise FileValidationError(
            f"El archivo de {empresa_label} ('{filename}') no contiene la hoja "
            f"requerida '{REQUIRED_SHEET}'."
        )


def _parse_sheet(excel_file: pd.ExcelFile, filename: str, empresa_label: str) -> pd.DataFrame:
    """Lee la hoja requerida como DataFrame controlando errores de lectura."""
    try:
        return excel_file.parse(REQUIRED_SHEET)
    except Exception as exc:
        logger.exception("Error leyendo la hoja %s de %s (%s)", REQUIRED_SHEET, empresa_label, filename)
        raise FileValidationError(
            f"No fue posible leer el contenido de la hoja '{REQUIRED_SHEET}' del "
            f"archivo de {empresa_label} ('{filename}')."
        ) from exc


def _validate_required_columns(df: pd.DataFrame, filename: str, empresa_label: str) -> None:
    """Verifica que existan las cuatro columnas requeridas para el cruce."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise FileValidationError(
            f"Al archivo de {empresa_label} ('{filename}') le faltan las siguientes "
            f"columnas requeridas: {', '.join(missing)}."
        )


def validate_key_values_present(df: pd.DataFrame, filename: str, empresa_label: str) -> None:
    """Verifica que existan filas con valores válidos para armar la llave de cruce."""
    longitud = pd.to_numeric(df["LONGITUD"], errors="coerce")
    latitud = pd.to_numeric(df["LATITUD"], errors="coerce")
    ident = df["IDENT_SECT_ESTAC_BASE_POR_TEC"].astype(str).str.strip()
    ident_valid = df["IDENT_SECT_ESTAC_BASE_POR_TEC"].notna() & (ident != "")

    valid_rows = longitud.notna() & latitud.notna() & ident_valid
    if not bool(valid_rows.any()):
        raise FileValidationError(
            f"El archivo de {empresa_label} ('{filename}') no tiene ninguna fila con "
            f"valores válidos de LONGITUD, LATITUD e IDENT_SECT_ESTAC_BASE_POR_TEC "
            f"para realizar el cruce."
        )


def validate_banda_convertible(df: pd.DataFrame, filename: str, empresa_label: str) -> None:
    """Verifica que la columna de banda tenga al menos un valor numérico válido."""
    banda = pd.to_numeric(df["BANDA_FRECUENCIA_OPERAC_SECTOR"], errors="coerce")
    if not bool(banda.notna().any()):
        raise FileValidationError(
            f"La columna BANDA_FRECUENCIA_OPERAC_SECTOR del archivo de "
            f"{empresa_label} ('{filename}') no contiene ningún valor numérico válido."
        )


def load_and_validate_sheet(
    file_obj: Union[BinaryIO, BytesIO], filename: str, empresa_label: str
) -> pd.DataFrame:
    """Ejecuta toda la cadena de validación y devuelve el DataFrame de la hoja.

    Orden de verificación: extensión, apertura del archivo, existencia de la
    hoja, lectura de la hoja, columnas requeridas, valores válidos de llave y
    convertibilidad de la banda.
    """
    validate_extension(filename, empresa_label)
    excel_file = _open_excel_file(file_obj, filename, empresa_label)
    _validate_sheet_present(excel_file, filename, empresa_label)
    df = _parse_sheet(excel_file, filename, empresa_label)
    _validate_required_columns(df, filename, empresa_label)
    validate_key_values_present(df, filename, empresa_label)
    validate_banda_convertible(df, filename, empresa_label)
    return df
