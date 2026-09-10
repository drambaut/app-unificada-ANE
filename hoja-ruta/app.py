from __future__ import annotations

import streamlit as st

from src import config
from src.dashboard import (
    apply_filters,
    render_articulation_chart,
    render_actividades_sin_cobertura,
    render_cobertura_lineas_chart,
    render_estado_cobertura_chart,
    render_kpis,
    render_matriz_proyecto_actividad,
    render_proyectos_por_actividad,
    render_tabla_detallada,
)
from src.data_loader import file_exists, load_csv


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px;}
        h1 {letter-spacing: 0;}
        .subtitle {font-size: 20px; color: #4B5563; margin-top: -0.4rem;}
        .note {
            color: #5F6B7A;
            background: #F6F8FA;
            border: 1px solid #E4E7EC;
            padding: 0.75rem 0.9rem;
            border-radius: 8px;
            margin: 0.8rem 0 1rem 0;
        }
        .kpi-card {
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            background: #FFFFFF;
            min-height: 88px;
        }
        .kpi-label {color: #667085; font-size: 0.82rem; line-height: 1.2; min-height: 2.1rem;}
        .kpi-value {color: #101828; font-size: 1.65rem; font-weight: 700; line-height: 1.1;}
        .matrix-wrap {
            width: 100%;
            max-height: 620px;
            overflow: auto;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            background: white;
        }
        .matrix-table {
            border-collapse: separate;
            border-spacing: 0;
            width: max-content;
            min-width: 100%;
            font-size: 0.72rem;
        }
        .matrix-table th {
            background: #F9FAFB;
            color: #344054;
            border: 1px solid #E5E7EB;
            padding: 0.45rem;
            vertical-align: middle;
            min-width: 150px;
            max-width: 220px;
            overflow-wrap: anywhere;
            position: sticky;
            top: 0;
            z-index: 2;
        }
        .matrix-table th:first-child {
            left: 0;
            z-index: 3;
            min-width: 320px;
            max-width: 420px;
            text-align: left;
        }
        .matrix-table tbody th {
            position: sticky;
            left: 0;
            z-index: 1;
            background: #FFFFFF;
            text-align: left;
        }
        .matrix-table td {
            border: 1px solid #E5E7EB;
            font-weight: 600;
            text-align: center;
            padding: 0.45rem;
            min-width: 150px;
            max-width: 220px;
        }
        .legend-dot {
            display: inline-block;
            width: 0.75rem;
            height: 0.75rem;
            border-radius: 50%;
            margin-left: 0.65rem;
            margin-right: 0.25rem;
            vertical-align: middle;
        }
        .legend-dot.cover {background: #2E7D32;}
        .legend-dot.partial {background: #F59E0B;}
        .legend-dot.none {background: #E5E7EB; border: 1px solid #9CA3AF;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.title("Cobertura de proyectos ED01-ED14 sobre las 29 actividades SGP")
    st.markdown(
        '<div class="subtitle">Mapa semantico proyecto x actividad para identificar que proyectos cubren, '
        "cubren parcialmente o no cubren cada actividad de la Hoja de Ruta.</div>",
        unsafe_allow_html=True,
    )


def render_missing_processed_file() -> None:
    st.info(
        "No se encontraron los archivos procesados requeridos:\n\n"
        "- data/processed/hoja_ruta.csv\n"
        "- data/processed/mapeo_generado.csv\n"
        "- data/processed/cobertura_actividades.csv\n\n"
        "Ejecuta primero:\n\n"
        "```bash\npython scripts/run_pipeline.py\n```"
    )


def main() -> None:
    inject_styles()
    render_header()

    required_files = [
        config.HOJA_RUTA_CSV,
        config.MAPEO_GENERADO_CSV,
        config.COBERTURA_ACTIVIDADES_CSV,
        config.PROYECTOS_RAW_CSV,
    ]
    if not all(file_exists(path) for path in required_files):
        render_missing_processed_file()
        return

    try:
        roadmap_df = load_csv(config.HOJA_RUTA_CSV)
        mapping_df = load_csv(config.MAPEO_GENERADO_CSV)
        summary_df = load_csv(config.COBERTURA_ACTIVIDADES_CSV)
        projects_df = load_csv(config.PROYECTOS_RAW_CSV)
    except Exception:
        st.error("No fue posible leer los archivos procesados. Ejecuta nuevamente python scripts/run_pipeline.py.")
        return

    filtered_summary, filtered_mapping = apply_filters(summary_df, mapping_df)
    render_kpis(filtered_summary)
    st.divider()
    render_articulation_chart(filtered_summary)
    st.divider()

    left, right = st.columns(2)
    with left:
        render_estado_cobertura_chart(filtered_summary)
    with right:
        render_cobertura_lineas_chart(filtered_summary)

    st.divider()
    render_proyectos_por_actividad(filtered_summary)

    st.divider()
    render_matriz_proyecto_actividad(filtered_mapping, roadmap_df, projects_df)

    st.divider()
    render_actividades_sin_cobertura(filtered_summary)

    st.divider()
    render_tabla_detallada(filtered_mapping)


if __name__ == "__main__":
    main()
