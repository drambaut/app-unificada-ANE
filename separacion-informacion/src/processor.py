"""Lógica de cruce entre los archivos de COLOMBIA MÓVIL y COLOMBIA TELECOMUNICACIONES.

La llave compuesta de cruce es (LONGITUD, LATITUD, IDENT_SECT_ESTAC_BASE_POR_TEC),
normalizada antes de comparar. Este módulo no depende de Streamlit y puede
probarse de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd

BANDA_OBJETIVO = 3580
COORD_DECIMALS = 6

_LON_COL = "LONGITUD"
_LAT_COL = "LATITUD"
_IDENT_COL = "IDENT_SECT_ESTAC_BASE_POR_TEC"
_BANDA_COL = "BANDA_FRECUENCIA_OPERAC_SECTOR"

_AUX_LON = "_lon_norm"
_AUX_LAT = "_lat_norm"
_AUX_IDENT = "_ident_norm"
_AUX_BANDA = "_banda_num"
_AUX_KEY = "_key"
_AUX_KEY_VALID = "_key_valid"


@dataclass
class ProcessingStats:
    """Estadísticas de control del cruce, para mostrar en la interfaz."""

    total_movil: int
    total_tel: int
    movil_key_valida: int
    tel_key_valida: int
    llaves_compartidas_unicas: int
    filas_ut5: int
    filas_ut: int
    filas_cmo: int
    filas_tel: int


@dataclass
class ProcessingResult:
    """Resultado completo del cruce: los cuatro DataFrames y las estadísticas."""

    ut5: pd.DataFrame
    ut: pd.DataFrame
    cmo: pd.DataFrame
    tel: pd.DataFrame
    stats: ProcessingStats


def _add_normalized_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia de `df` con columnas auxiliares de llave normalizada.

    - LONGITUD/LATITUD se convierten a numérico y se redondean a
      `COORD_DECIMALS` decimales para evitar diferencias por representación
      de punto flotante.
    - IDENT_SECT_ESTAC_BASE_POR_TEC se recorta de espacios y se compara como
      texto.
    - BANDA_FRECUENCIA_OPERAC_SECTOR se convierte a numérico.
    - Una fila tiene llave válida solo si LONGITUD, LATITUD e IDENT no son
      nulos tras la normalización.
    """
    working = df.copy()

    working[_AUX_LON] = pd.to_numeric(working[_LON_COL], errors="coerce").round(COORD_DECIMALS)
    working[_AUX_LAT] = pd.to_numeric(working[_LAT_COL], errors="coerce").round(COORD_DECIMALS)

    ident_str = working[_IDENT_COL].astype(str).str.strip()
    ident_is_null = working[_IDENT_COL].isna() | (ident_str == "")
    working[_AUX_IDENT] = ident_str.mask(ident_is_null)

    working[_AUX_BANDA] = pd.to_numeric(working[_BANDA_COL], errors="coerce")

    working[_AUX_KEY_VALID] = (
        working[_AUX_LON].notna() & working[_AUX_LAT].notna() & working[_AUX_IDENT].notna()
    )
    working[_AUX_KEY] = list(zip(working[_AUX_LON], working[_AUX_LAT], working[_AUX_IDENT]))

    return working


def _unique_valid_keys(working: pd.DataFrame) -> set:
    """Extrae el conjunto de llaves únicas y válidas de un DataFrame preparado."""
    return set(working.loc[working[_AUX_KEY_VALID], _AUX_KEY])


def _shared_mask(working: pd.DataFrame, other_keys: set) -> pd.Series:
    """Máscara booleana: fila tiene llave válida y esa llave existe en `other_keys`."""
    return working[_AUX_KEY_VALID] & working[_AUX_KEY].isin(other_keys)


def _assert_no_banda_objetivo(df: pd.DataFrame, result_name: str) -> None:
    """Verifica que `df` no contenga ninguna fila con banda == BANDA_OBJETIVO.

    UT5 es el único resultado que puede contener banda 3580. Se recalcula la
    versión numérica de la columna (para soportar valores como 3580, 3580.0
    o "3580") en lugar de confiar en el tipo original de la celda.
    """
    banda_numeric = pd.to_numeric(df[_BANDA_COL], errors="coerce")
    assert not bool((banda_numeric == BANDA_OBJETIVO).any()), (
        f"Invariante violada: {result_name}.xlsx contiene filas con "
        f"BANDA_FRECUENCIA_OPERAC_SECTOR == {BANDA_OBJETIVO}, pero UT5 debe "
        f"ser el único resultado que pueda contenerlas."
    )


def process_files(df_movil: pd.DataFrame, df_tel: pd.DataFrame) -> ProcessingResult:
    """Cruza los archivos de COLOMBIA MÓVIL y COLOMBIA TELECOMUNICACIONES.

    Devuelve los cuatro subconjuntos (UT5, UT, CMO, TEL) como subconjuntos
    fieles de las filas y columnas originales, más las estadísticas de
    control del cruce. No se realiza ningún `merge` que pueda multiplicar
    filas: la pertenencia a la otra tabla se resuelve contra un conjunto de
    llaves únicas.
    """
    movil_work = _add_normalized_key_columns(df_movil)
    tel_work = _add_normalized_key_columns(df_tel)

    movil_keys = _unique_valid_keys(movil_work)
    tel_keys = _unique_valid_keys(tel_work)

    shared_movil = _shared_mask(movil_work, tel_keys)
    shared_tel = _shared_mask(tel_work, movil_keys)

    banda_movil = movil_work[_AUX_BANDA]
    banda_tel = tel_work[_AUX_BANDA]

    ut5_mask = shared_movil & (banda_movil == BANDA_OBJETIVO)
    ut_mask = shared_movil & (banda_movil != BANDA_OBJETIVO)
    cmo_mask = (~shared_movil) & (banda_movil != BANDA_OBJETIVO)
    tel_mask = (~shared_tel) & (banda_tel != BANDA_OBJETIVO)

    ut5 = df_movil.loc[ut5_mask].copy()
    ut = df_movil.loc[ut_mask].copy()
    cmo = df_movil.loc[cmo_mask].copy()
    tel = df_tel.loc[tel_mask].copy()

    _assert_no_banda_objetivo(ut, "UT")
    _assert_no_banda_objetivo(cmo, "CMO")
    _assert_no_banda_objetivo(tel, "TEL")

    stats = ProcessingStats(
        total_movil=len(df_movil),
        total_tel=len(df_tel),
        movil_key_valida=int(movil_work[_AUX_KEY_VALID].sum()),
        tel_key_valida=int(tel_work[_AUX_KEY_VALID].sum()),
        llaves_compartidas_unicas=len(movil_keys & tel_keys),
        filas_ut5=len(ut5),
        filas_ut=len(ut),
        filas_cmo=len(cmo),
        filas_tel=len(tel),
    )

    return ProcessingResult(ut5=ut5, ut=ut, cmo=cmo, tel=tel, stats=stats)
