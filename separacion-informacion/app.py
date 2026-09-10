"""Aplicación Streamlit para cruzar estaciones base de COLOMBIA MÓVIL y
COLOMBIA TELECOMUNICACIONES y generar los archivos UT5, UT, CMO y TEL.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from src.exporters import build_result_files, build_zip_bytes
from src.processor import ProcessingResult, process_files
from src.validators import FileValidationError, load_and_validate_sheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MOVIL_LABEL = "COLOMBIA MÓVIL S.A. E.S.P."
TEL_LABEL = "COLOMBIA TELECOMUNICACIONES S.A. E.S.P."

RESULT_LABELS = {
    "UT5.xlsx": "UT5 (compartidas, banda = 3580)",
    "UT.xlsx": "UT (compartidas, banda ≠ 3580)",
    "CMO.xlsx": "CMO (solo COLOMBIA MÓVIL, banda ≠ 3580)",
    "TEL.xlsx": "TEL (solo COLOMBIA TELECOMUNICACIONES, banda ≠ 3580)",
}

ZIP_NAME = "resultados_cruce_estaciones_base.zip"


def _build_control_table(result: ProcessingResult) -> pd.DataFrame:
    """Arma la tabla de control con las métricas del cruce."""
    stats = result.stats
    rows = [
        ("Total de filas COLOMBIA MÓVIL", stats.total_movil),
        ("Total de filas COLOMBIA TELECOMUNICACIONES", stats.total_tel),
        ("Filas COLOMBIA MÓVIL con llave válida", stats.movil_key_valida),
        ("Filas COLOMBIA TELECOMUNICACIONES con llave válida", stats.tel_key_valida),
        ("Llaves compartidas únicas", stats.llaves_compartidas_unicas),
        ("Filas en UT5.xlsx", stats.filas_ut5),
        ("Filas en UT.xlsx", stats.filas_ut),
        ("Filas en CMO.xlsx", stats.filas_cmo),
        ("Filas en TEL.xlsx", stats.filas_tel),
    ]
    return pd.DataFrame(rows, columns=["Métrica", "Valor"])


def _run_pipeline(movil_file, tel_file) -> None:
    """Valida, procesa y guarda los resultados en `st.session_state`."""
    with st.spinner("Leyendo y validando archivos..."):
        df_movil = load_and_validate_sheet(movil_file, movil_file.name, MOVIL_LABEL)
        df_tel = load_and_validate_sheet(tel_file, tel_file.name, TEL_LABEL)

    with st.spinner("Cruzando estaciones base..."):
        result = process_files(df_movil, df_tel)

    with st.spinner("Generando archivos Excel..."):
        dataframes = {
            "UT5.xlsx": result.ut5,
            "UT.xlsx": result.ut,
            "CMO.xlsx": result.cmo,
            "TEL.xlsx": result.tel,
        }
        files = build_result_files(dataframes)
        zip_bytes = build_zip_bytes(files)

    st.session_state["sep_result_files"] = files
    st.session_state["sep_zip_bytes"] = zip_bytes
    st.session_state["sep_control_table"] = _build_control_table(result)
    st.session_state["sep_previews"] = {name: df.head(20) for name, df in dataframes.items()}
    st.session_state["sep_row_counts"] = {name: len(df) for name, df in dataframes.items()}


def _render_results() -> None:
    """Muestra resumen, tabla de control, vistas previas y descargas."""
    st.success("Archivos procesados correctamente.")

    st.subheader("Resumen de resultados")
    counts = st.session_state["sep_row_counts"]
    cols = st.columns(4)
    for col, (name, _) in zip(cols, RESULT_LABELS.items()):
        col.metric(name.replace(".xlsx", ""), counts[name])

    st.subheader("Tabla de control")
    st.dataframe(st.session_state["sep_control_table"], hide_index=True, use_container_width=True)

    st.subheader("Vista previa de resultados")
    tabs = st.tabs(list(RESULT_LABELS.values()))
    for tab, name in zip(tabs, RESULT_LABELS.keys()):
        with tab:
            preview = st.session_state["sep_previews"][name]
            if preview.empty:
                st.info("Este resultado no tiene filas.")
            else:
                st.dataframe(preview, use_container_width=True)

    st.subheader("Descargas")
    files = st.session_state["sep_result_files"]
    download_cols = st.columns(4)
    for col, (name, label) in zip(download_cols, RESULT_LABELS.items()):
        col.download_button(
            label=f"Descargar {name}",
            data=files[name],
            file_name=name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{name}",
        )

    st.download_button(
        label="Descargar los 4 resultados en ZIP",
        data=st.session_state["sep_zip_bytes"],
        file_name=ZIP_NAME,
        mime="application/zip",
        key="download_zip",
    )


def main() -> None:
    """Punto de entrada de la aplicación Streamlit."""
    st.title("Cruce de Estaciones Base — TIGO / TELECOMUNICACIONES")

    st.markdown(
        """
        Esta aplicación cruza las estaciones base reportadas por **COLOMBIA MÓVIL**
        y **COLOMBIA TELECOMUNICACIONES** usando como llave compuesta
        `LONGITUD + LATITUD + IDENT_SECT_ESTAC_BASE_POR_TEC` (coordenadas
        redondeadas a 6 decimales, identificador comparado como texto sin
        espacios). Según si la estación es compartida y el valor de
        `BANDA_FRECUENCIA_OPERAC_SECTOR`, cada fila se clasifica en uno de
        cuatro archivos: **UT5**, **UT**, **CMO** o **TEL**.
        """
    )
    st.markdown("<div style='height:2.5em'></div>", unsafe_allow_html=True)

    col_movil, col_tel = st.columns(2)
    with col_movil:
        st.markdown(f"<p style=\"font-size:22px; font-weight:700;\">Archivo de {MOVIL_LABEL}</p>", unsafe_allow_html=True)
        movil_file = st.file_uploader(
            "Cargar archivo de COLOMBIA MÓVIL", type=["xlsx", "xls"], key="movil_uploader"
        )
    with col_tel:
        st.markdown(f"<p style=\"font-size:22px; font-weight:700;\">Archivo de {TEL_LABEL}</p>", unsafe_allow_html=True)
        tel_file = st.file_uploader(
            "Cargar archivo de COLOMBIA TELECOMUNICACIONES", type=["xlsx", "xls"], key="tel_uploader"
        )

    if st.button("Procesar archivos", type="primary"):
        if movil_file is None or tel_file is None:
            st.error("Debe cargar ambos archivos antes de procesar: COLOMBIA MÓVIL y COLOMBIA TELECOMUNICACIONES.")
        else:
            try:
                _run_pipeline(movil_file, tel_file)
            except FileValidationError as exc:
                st.error(str(exc))
            except Exception:
                logger.exception("Error inesperado procesando los archivos")
                st.error(
                    "Ocurrió un error inesperado al procesar los archivos. "
                    "Verifique que los archivos correspondan al formato esperado "
                    "e inténtelo nuevamente."
                )

    if "sep_result_files" in st.session_state:
        _render_results()


if __name__ == "__main__":
    main()
