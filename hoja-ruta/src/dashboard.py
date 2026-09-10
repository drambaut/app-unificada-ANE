from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.coverage_model import build_project_activity_matrix


RELATION_ORDER = ["Cubre", "Cubre parcialmente", "No cubre"]
COVERAGE_ORDER = ["Cubierta", "Parcialmente cubierta", "Sin cobertura"]

RELATION_COLORS = {
    "Cubre": "#2E7D32",
    "Cubre parcialmente": "#F59E0B",
    "No cubre": "#E5E7EB",
}

COVERAGE_COLORS = {
    "Cubierta": "#2E7D32",
    "Parcialmente cubierta": "#F59E0B",
    "Sin cobertura": "#9CA3AF",
}

SHORT_LABELS = {
    "Cubre": "Si",
    "Cubre parcialmente": "Parcial",
    "No cubre": "No",
}

ARTICULATION_CONTRIBUTION_TEXT = {
    "Cubierta": "Contribuye de forma directa a la estrategia.",
    "Parcialmente cubierta": "Contribuye de forma parcial y complementaria.",
    "Sin cobertura": "Actividad prevista en la estrategia con cobertura pendiente.",
}

ARTICULATION_LINE_LABELS = {
    "Arquitectura, integracion y almacenamiento de datos": "Arquitectura",
    "Arquitectura, integración y almacenamiento de datos": "Arquitectura",
    "Gobernanza de datos": "Gobernanza",
    "Analitica de datos": "Analitica",
    "Analítica de datos": "Analitica",
    "Optimizacion": "Optimizacion",
    "Optimización": "Optimizacion",
    "Cultura organizacional en torno a la gestion de datos": "Cultura",
    "Cultura organizacional en torno a la gestión de datos": "Cultura",
}

ARTICULATION_LINE_COLORS = {
    "Arquitectura": "#F59E0B",
    "Gobernanza": "#EF4444",
    "Analitica": "#10B981",
    "Optimizacion": "#3B82F6",
    "Cultura": "#8B5CF6",
}

ARTICULATION_STATUS_LABELS = {
    "Cubierta": "Contribuye",
    "Parcialmente cubierta": "Complementa",
    "Sin cobertura": "Requiere fortalecimiento",
}

ARTICULATION_LINE_CONTEXT = {
    "Arquitectura": "Organiza fuentes, integracion y almacenamiento para sostener la estrategia.",
    "Gobernanza": "Define reglas, responsables y estandares para la gestion de datos.",
    "Analitica": "Transforma la informacion en seguimiento, tableros y valor para la Subdireccion.",
    "Optimizacion": "Conecta los datos con eficiencia operativa y trazabilidad.",
    "Cultura": "Sostiene apropiacion, documentacion y capacidades de uso.",
}


def apply_filters(summary_df: pd.DataFrame, mapping_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    st.subheader("Filtros")
    filtered_summary = summary_df.copy()
    filtered_mapping = mapping_df.copy()
    cols = st.columns(4)

    line_options = sorted(filtered_summary["linea_hoja_ruta"].dropna().astype(str).unique())
    state_options = sorted(filtered_summary["estado_cobertura"].dropna().astype(str).unique())
    project_options = sorted(filtered_mapping["codigo_proyecto"].dropna().astype(str).unique())
    relation_options = RELATION_ORDER

    selected_lines = cols[0].multiselect("Linea", options=line_options)
    selected_states = cols[1].multiselect("Cobertura actividad", options=state_options)
    selected_projects = cols[2].multiselect("Proyecto", options=project_options)
    selected_relations = cols[3].multiselect("Estado relacion", options=relation_options)

    if selected_lines:
        filtered_summary = filtered_summary[filtered_summary["linea_hoja_ruta"].astype(str).isin(selected_lines)]
    if selected_states:
        filtered_summary = filtered_summary[filtered_summary["estado_cobertura"].astype(str).isin(selected_states)]

    allowed_activities = set(filtered_summary["id_actividad"].astype(str))
    filtered_mapping = filtered_mapping[filtered_mapping["id_actividad"].astype(str).isin(allowed_activities)]

    if selected_projects:
        filtered_mapping = filtered_mapping[filtered_mapping["codigo_proyecto"].astype(str).isin(selected_projects)]
    if selected_relations:
        filtered_mapping = filtered_mapping[filtered_mapping["estado_relacion"].astype(str).isin(selected_relations)]

    if selected_projects or selected_relations:
        allowed_activities = set(filtered_mapping["id_actividad"].astype(str))
        filtered_summary = filtered_summary[filtered_summary["id_actividad"].astype(str).isin(allowed_activities)]

    return filtered_summary, filtered_mapping


def render_kpis(summary_df: pd.DataFrame) -> None:
    total = len(summary_df)
    counts = summary_df["estado_cobertura"].value_counts()
    covered = int(counts.get("Cubierta", 0))
    partial = int(counts.get("Parcialmente cubierta", 0))
    uncovered = int(counts.get("Sin cobertura", 0))
    coverage_pct = ((covered + 0.5 * partial) / total * 100) if total else 0

    kpis = [
        ("Total actividades", total),
        ("Cubiertas", covered),
        ("Parcialmente cubiertas", partial),
        ("Sin cobertura", uncovered),
        ("% cobertura", f"{coverage_pct:.1f}%"),
    ]

    cols = st.columns(5)
    for col, (label, value) in zip(cols, kpis):
        col.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{html.escape(label)}</div>
                <div class="kpi-value">{html.escape(str(value))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.caption(
        "Formula: (actividades cubiertas + 0.5 x actividades parcialmente cubiertas) / 29 x 100. "
        "El mapeo analiza correspondencia tematica y de alcance, no avance ni ejecucion."
    )


def build_articulation_view(summary_df: pd.DataFrame) -> pd.DataFrame:
    articulation = summary_df[
        ["id_actividad", "linea_hoja_ruta", "actividad", "estado_cobertura"]
    ].copy()

    if articulation.empty:
        return articulation

    articulation["estrategia"] = "Estrategia de datos"
    articulation["linea_label"] = (
        articulation["linea_hoja_ruta"]
        .astype(str)
        .map(ARTICULATION_LINE_LABELS)
        .fillna(articulation["linea_hoja_ruta"].astype(str))
    )
    articulation["actividad_label"] = articulation["id_actividad"].astype(str)
    articulation["aporte_actual"] = (
        articulation["estado_cobertura"].map(ARTICULATION_CONTRIBUTION_TEXT).fillna("Relacion no clasificada.")
    )
    articulation["peso"] = 1
    articulation = articulation.sort_values(["linea_hoja_ruta", "id_actividad"]).reset_index(drop=True)
    return articulation


def build_articulation_nodes(summary_df: pd.DataFrame) -> pd.DataFrame:
    articulation = build_articulation_view(summary_df)
    if articulation.empty:
        return articulation

    nodes: list[dict[str, object]] = []
    total = len(articulation)
    total_covered = int((articulation["estado_cobertura"] == "Cubierta").sum())
    total_partial = int((articulation["estado_cobertura"] == "Parcialmente cubierta").sum())
    total_uncovered = int((articulation["estado_cobertura"] == "Sin cobertura").sum())

    nodes.append(
        {
            "id": "estrategia",
            "parent": "",
            "label": "Estrategia",
            "full_label": "Estrategia de datos de la Subdireccion",
            "value": total,
            "color": "#22C55E",
            "coverage_text": f"Actividades analizadas: {total}",
            "interpretation": "Integra las lineas y actividades de la hoja de ruta.",
            "detail": (
                f"Cubiertas: {total_covered} | Parciales: {total_partial} | "
                f"Sin cobertura: {total_uncovered}"
            ),
        }
    )

    for line_label, line_group in articulation.groupby("linea_label", sort=False):
        covered = int((line_group["estado_cobertura"] == "Cubierta").sum())
        partial = int((line_group["estado_cobertura"] == "Parcialmente cubierta").sum())
        uncovered = int((line_group["estado_cobertura"] == "Sin cobertura").sum())
        nodes.append(
            {
                "id": f"linea::{line_label}",
                "parent": "estrategia",
                "label": line_label,
                "full_label": str(line_group["linea_hoja_ruta"].iloc[0]),
                "value": len(line_group),
                "color": ARTICULATION_LINE_COLORS.get(line_label, "#64748B"),
                "coverage_text": (
                    f"Actividades: {len(line_group)} | Cubiertas: {covered} | "
                    f"Parciales: {partial} | Sin cobertura: {uncovered}"
                ),
                "interpretation": ARTICULATION_LINE_CONTEXT.get(
                    line_label,
                    "Agrupa actividades que aportan a la estrategia de datos.",
                ),
                "detail": "Haz clic para enfocar esta linea y revisar sus actividades.",
            }
        )

        for row in line_group.itertuples():
            status = str(row.estado_cobertura)
            nodes.append(
                {
                    "id": f"actividad::{row.id_actividad}",
                    "parent": f"linea::{line_label}",
                    "label": str(row.id_actividad),
                    "full_label": str(row.actividad),
                    "value": 1,
                    "color": COVERAGE_COLORS.get(status, "#9CA3AF"),
                    "coverage_text": f"Cobertura actual: {status}",
                    "interpretation": ARTICULATION_STATUS_LABELS.get(status, "Relacion no clasificada"),
                    "detail": ARTICULATION_CONTRIBUTION_TEXT.get(status, "Sin detalle disponible."),
                }
            )

    return pd.DataFrame(nodes)


def render_articulation_chart(summary_df: pd.DataFrame) -> None:
    st.subheader("Mapa jerarquico de articulacion")
    st.caption(
        "Visualizacion basada en el proyecto para mostrar como cada actividad aporta a la estrategia. "
        "Verde: contribuye. Amarillo: complementa. Gris: requiere fortalecimiento."
    )
    st.markdown(
        """
        <div class="note">
        <strong>Leyenda del grafico:</strong>
        <span class="legend-dot cover"></span> Contribuye
        <span class="legend-dot partial"></span> Complementa
        <span class="legend-dot none"></span> Requiere fortalecimiento
        </div>
        """,
        unsafe_allow_html=True,
    )

    articulation = build_articulation_view(summary_df)
    nodes = build_articulation_nodes(summary_df)
    if articulation.empty or nodes.empty:
        st.info("No hay actividades para mostrar en el filtro actual.")
        return

    fig = go.Figure(
        go.Sunburst(
            ids=nodes["id"],
            labels=nodes["label"],
            parents=nodes["parent"],
            values=nodes["value"],
            branchvalues="total",
            marker=dict(colors=nodes["color"], line=dict(color="#111827", width=1)),
            customdata=nodes[["full_label", "coverage_text", "interpretation", "detail"]],
            maxdepth=3,
        )
    )
    fig.update_traces(
        insidetextorientation="horizontal",
        textinfo="label",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "%{customdata[0]}<br>"
            "%{customdata[1]}<br>"
            "%{customdata[2]}<br>"
            "%{customdata[3]}<extra></extra>"
        ),
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=720,
        font=dict(size=14),
        uniformtext=dict(minsize=11, mode="hide"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        <div class="note">
        <strong>Lectura del grafico:</strong>
        Verde = la actividad contribuye de forma directa.
        Amarillo = la actividad complementa la estrategia de forma parcial.
        Gris = la actividad sigue siendo una brecha o frente por fortalecer.
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Referencia de actividades del grafico"):
        reference = articulation[
            ["id_actividad", "actividad", "linea_hoja_ruta", "estado_cobertura"]
        ].rename(
            columns={
                "id_actividad": "Actividad",
                "actividad": "Descripcion",
                "linea_hoja_ruta": "Linea",
                "estado_cobertura": "Cobertura",
            }
        )
        st.dataframe(reference, use_container_width=True, hide_index=True)


def render_estado_cobertura_chart(summary_df: pd.DataFrame) -> None:
    st.subheader("Distribucion de cobertura")
    data = (
        summary_df["estado_cobertura"]
        .value_counts()
        .reindex(COVERAGE_ORDER, fill_value=0)
        .reset_index()
    )
    data.columns = ["estado_cobertura", "cantidad"]
    data = data[data["cantidad"] > 0]
    fig = px.pie(
        data,
        names="estado_cobertura",
        values="cantidad",
        hole=0.55,
        color="estado_cobertura",
        color_discrete_map=COVERAGE_COLORS,
    )
    fig.update_traces(textposition="inside", textinfo="label+value")
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


def render_cobertura_lineas_chart(summary_df: pd.DataFrame) -> None:
    st.subheader("Cobertura por linea")
    data = (
        summary_df.groupby(["linea_hoja_ruta", "estado_cobertura"])
        .size()
        .reset_index(name="actividades")
    )
    fig = px.bar(
        data,
        x="actividades",
        y="linea_hoja_ruta",
        color="estado_cobertura",
        orientation="h",
        text="actividades",
        color_discrete_map=COVERAGE_COLORS,
        category_orders={"estado_cobertura": COVERAGE_ORDER},
    )
    fig.update_layout(xaxis_title="Actividades", yaxis_title="", legend_title_text="Estado")
    st.plotly_chart(fig, use_container_width=True)


def render_proyectos_por_actividad(summary_df: pd.DataFrame) -> None:
    st.subheader("Cantidad de proyectos que cubren cada actividad")
    data = summary_df.copy()
    data["proyectos_con_relacion"] = (
        data["total_proyectos_que_cubren"].astype(int)
        + data["total_proyectos_parciales"].astype(int)
    )
    fig = px.bar(
        data.sort_values("proyectos_con_relacion", ascending=True),
        x="proyectos_con_relacion",
        y="id_actividad",
        orientation="h",
        text="proyectos_con_relacion",
        color="estado_cobertura",
        color_discrete_map=COVERAGE_COLORS,
        hover_data=["actividad", "proyectos_que_cubren", "proyectos_parciales"],
    )
    fig.update_layout(xaxis_title="Proyectos con cobertura total o parcial", yaxis_title="Actividad", height=760)
    st.plotly_chart(fig, use_container_width=True)


def render_legend() -> None:
    st.markdown(
        """
        <div class="note">
        <strong>Leyenda:</strong>
        <span class="legend-dot cover"></span> Cubre: el proyecto contempla sustancialmente la actividad.
        <span class="legend-dot partial"></span> Cubre parcialmente: contempla solo una parte de la actividad.
        <span class="legend-dot none"></span> No cubre: el proyecto no contempla la actividad.
        Este mapeo analiza correspondencia tematica y de alcance, no avance ni ejecucion del proyecto.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_matriz_proyecto_actividad(mapping_df: pd.DataFrame, roadmap_df: pd.DataFrame, projects_df: pd.DataFrame) -> None:
    st.subheader("Matriz Proyecto x Actividad")
    render_legend()
    matrix = build_project_activity_matrix(mapping_df, roadmap_df, projects_df)

    activity_text = {
        f"{row.id_actividad} - {row.actividad}": row.actividad
        for row in roadmap_df.itertuples()
    }
    justification_lookup = {
        (f"{row.codigo_proyecto} - {row.nombre_proyecto}", f"{row.id_actividad} - {row.actividad}"): row.justificacion
        for row in mapping_df.itertuples()
    }

    table = ['<div class="matrix-wrap"><table class="matrix-table">']
    table.append("<thead><tr><th>Proyecto</th>")
    for column in matrix.columns:
        table.append(f"<th title=\"{html.escape(column)}\">{html.escape(column)}</th>")
    table.append("</tr></thead><tbody>")

    for project_label, row in matrix.iterrows():
        table.append(f"<tr><th>{html.escape(str(project_label))}</th>")
        for column, state in row.items():
            state_text = str(state)
            short = SHORT_LABELS.get(state_text, state_text)
            color = RELATION_COLORS.get(state_text, "#E5E7EB")
            text_color = "#111827" if state_text == "No cubre" else "#FFFFFF"
            reason = justification_lookup.get((project_label, column), "")
            tooltip = (
                f"Proyecto: {project_label}\n"
                f"Actividad: {column}\n"
                f"Resultado: {state_text}\n"
                f"Razon: {reason}"
            )
            table.append(
                f'<td style="background:{color}; color:{text_color};" title="{html.escape(tooltip)}">'
                f"{html.escape(short)}</td>"
            )
        table.append("</tr>")

    table.append("</tbody></table></div>")
    st.markdown("".join(table), unsafe_allow_html=True)

    with st.expander("Referencia de actividades"):
        reference = roadmap_df[["id_actividad", "actividad", "linea_hoja_ruta"]].copy()
        reference["Referencia"] = reference["id_actividad"] + " - " + reference["actividad"]
        st.dataframe(reference[["Referencia", "linea_hoja_ruta"]], use_container_width=True, hide_index=True)


def render_actividades_sin_cobertura(summary_df: pd.DataFrame) -> None:
    st.subheader("Actividades sin cobertura")
    uncovered = summary_df[summary_df["estado_cobertura"] == "Sin cobertura"]
    if uncovered.empty:
        st.success("No hay actividades sin cobertura en el filtro actual.")
        return
    st.dataframe(
        uncovered[["id_actividad", "linea_hoja_ruta", "actividad"]],
        use_container_width=True,
        hide_index=True,
    )


def render_tabla_detallada(mapping_df: pd.DataFrame) -> None:
    st.subheader("Tabla detallada")
    if mapping_df.empty:
        st.info("No hay pares proyecto-actividad para mostrar.")
        return
    table = mapping_df.copy()
    table["Proyecto"] = table["codigo_proyecto"] + " - " + table["nombre_proyecto"]
    table["Actividad"] = table["id_actividad"] + " - " + table["actividad"]
    table = table.rename(columns={"estado_relacion": "Estado", "justificacion": "Justificacion"})
    st.dataframe(
        table[["Proyecto", "Actividad", "linea_hoja_ruta", "Estado", "Justificacion"]],
        use_container_width=True,
        hide_index=True,
    )
