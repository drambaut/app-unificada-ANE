"""Pruebas unitarias para la lógica de cruce en `src.processor`."""

from __future__ import annotations

import pandas as pd
import pytest

from src.processor import BANDA_OBJETIVO, process_files

COLUMNS = [
    "LONGITUD",
    "LATITUD",
    "IDENT_SECT_ESTAC_BASE_POR_TEC",
    "BANDA_FRECUENCIA_OPERAC_SECTOR",
    "OTRO_CAMPO",
]


def _row(lon, lat, ident, banda, otro="x"):
    return {
        "LONGITUD": lon,
        "LATITUD": lat,
        "IDENT_SECT_ESTAC_BASE_POR_TEC": ident,
        "BANDA_FRECUENCIA_OPERAC_SECTOR": banda,
        "OTRO_CAMPO": otro,
    }


def _df(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def test_fila_compartida_banda_3580_va_a_ut5():
    movil = _df([_row(-74.1, 4.6, "SECT-1", 3580)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 2100)])

    result = process_files(movil, tel)

    assert len(result.ut5) == 1
    assert len(result.ut) == 0
    assert len(result.cmo) == 0


def test_fila_compartida_otra_banda_va_a_ut():
    movil = _df([_row(-74.1, 4.6, "SECT-1", 2100)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 3580)])

    result = process_files(movil, tel)

    assert len(result.ut) == 1
    assert len(result.ut5) == 0
    assert len(result.cmo) == 0


def test_fila_unica_movil_banda_diferente_va_a_cmo():
    movil = _df([_row(-74.1, 4.6, "SECT-1", 2100)])
    tel = _df([_row(-75.0, 5.0, "OTRA", 2100)])

    result = process_files(movil, tel)

    assert len(result.cmo) == 1
    assert len(result.ut5) == 0
    assert len(result.ut) == 0


def test_fila_unica_tel_banda_diferente_va_a_tel():
    movil = _df([_row(-75.0, 5.0, "OTRA", 2100)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 2100)])

    result = process_files(movil, tel)

    assert len(result.tel) == 1


def test_fila_unica_tel_banda_3580_no_va_a_tel():
    """TEL excluye banda 3580: UT5 es el único resultado que puede contenerla."""
    movil = _df([_row(-75.0, 5.0, "OTRA", 2100)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 3580)])

    result = process_files(movil, tel)

    assert len(result.tel) == 0


def test_ut5_es_el_unico_resultado_que_puede_contener_banda_3580():
    """Con una mezcla de filas compartidas y no compartidas en banda 3580 y
    otras bandas, solo UT5 debe recibir filas con banda == 3580."""
    movil = _df(
        [
            _row(-74.1, 4.6, "SECT-1", 3580, otro="movil_compartida_3580"),
            _row(-74.1, 4.6, "SECT-1", 2100, otro="movil_compartida_otra"),
            _row(-75.0, 5.0, "UNICA-M", 3580, otro="movil_unica_3580"),
            _row(-75.0, 5.0, "UNICA-M", 2100, otro="movil_unica_otra"),
        ]
    )
    tel = _df(
        [
            _row(-74.1, 4.6, "SECT-1", 2100, otro="tel_compartida"),
            _row(-76.0, 6.0, "UNICA-T", 3580, otro="tel_unica_3580"),
            _row(-76.0, 6.0, "UNICA-T2", 2100, otro="tel_unica_otra"),
        ]
    )

    result = process_files(movil, tel)

    for nombre, df in (("UT", result.ut), ("CMO", result.cmo), ("TEL", result.tel)):
        banda_numerica = pd.to_numeric(df["BANDA_FRECUENCIA_OPERAC_SECTOR"], errors="coerce")
        assert not (banda_numerica == BANDA_OBJETIVO).any(), f"{nombre} no debe contener banda 3580"

    assert (
        pd.to_numeric(result.ut5["BANDA_FRECUENCIA_OPERAC_SECTOR"], errors="coerce") == BANDA_OBJETIVO
    ).all()
    assert len(result.ut5) == 1


def test_fila_unica_movil_banda_3580_no_va_a_ningun_resultado_de_movil():
    """No compartida y banda == 3580 no cumple ninguna condición de UT5/UT/CMO."""
    movil = _df([_row(-75.0, 5.0, "OTRA", 3580)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 2100)])

    result = process_files(movil, tel)

    assert len(result.ut5) == 0
    assert len(result.ut) == 0
    assert len(result.cmo) == 0


def test_llaves_duplicadas_no_multiplican_filas():
    movil = _df(
        [
            _row(-74.1, 4.6, "SECT-1", 3580),
            _row(-74.1, 4.6, "SECT-1", 3580),
        ]
    )
    tel = _df(
        [
            _row(-74.1, 4.6, "SECT-1", 2100),
            _row(-74.1, 4.6, "SECT-1", 2100),
            _row(-74.1, 4.6, "SECT-1", 2100),
        ]
    )

    result = process_files(movil, tel)

    assert len(result.ut5) == 2
    assert result.stats.llaves_compartidas_unicas == 1


def test_redondeo_de_coordenadas_hace_coincidir_llaves():
    movil = _df([_row(-74.100000499, 4.600000499, "SECT-1", 3580)])
    tel = _df([_row(-74.1000001, 4.6000001, "SECT-1", 2100)])

    result = process_files(movil, tel)

    assert len(result.ut5) == 1


def test_llaves_incompletas_no_se_consideran_compartidas():
    movil = _df([_row(None, 4.6, "SECT-1", 2100)])
    tel = _df([_row(None, 4.6, "SECT-1", 3580)])

    result = process_files(movil, tel)

    assert len(result.cmo) == 1
    assert len(result.ut) == 0
    assert len(result.ut5) == 0


def test_resultados_vacios_conservan_encabezados():
    movil = _df([])
    tel = _df([])

    result = process_files(movil, tel)

    assert list(result.ut5.columns) == COLUMNS
    assert list(result.ut.columns) == COLUMNS
    assert list(result.cmo.columns) == COLUMNS
    assert list(result.tel.columns) == COLUMNS
    assert len(result.ut5) == 0


def test_columnas_auxiliares_no_aparecen_en_resultados():
    movil = _df([_row(-74.1, 4.6, "SECT-1", 3580)])
    tel = _df([_row(-74.1, 4.6, "SECT-1", 2100)])

    result = process_files(movil, tel)

    for df in (result.ut5, result.ut, result.cmo, result.tel):
        assert list(df.columns) == COLUMNS
        assert not any(col.startswith("_") for col in df.columns)


def test_orden_original_de_filas_y_columnas_se_conserva():
    movil = _df(
        [
            _row(-74.1, 4.6, "SECT-1", 2100, otro="primero"),
            _row(-74.1, 4.6, "SECT-1", 2100, otro="segundo"),
            _row(-74.2, 4.7, "SECT-2", 2100, otro="tercero"),
        ]
    )
    tel = _df([_row(-74.1, 4.6, "SECT-1", 3580), _row(-74.2, 4.7, "SECT-2", 3580)])

    result = process_files(movil, tel)

    assert list(result.ut["OTRO_CAMPO"]) == ["primero", "segundo", "tercero"]
    assert list(result.ut.columns) == COLUMNS
