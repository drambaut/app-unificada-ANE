from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_loader import save_csv_atomic


EXPECTED_ACTIVITY_COUNT = 29

ROADMAP_COLUMNS = [
    "id_actividad",
    "linea_hoja_ruta",
    "actividad",
    "horizonte",
    "observaciones",
]

MAPPING_COLUMNS = [
    "codigo_proyecto",
    "nombre_proyecto",
    "id_actividad",
    "linea_hoja_ruta",
    "actividad",
    "estado_relacion",
    "justificacion",
]

COVERAGE_COLUMNS = [
    "id_actividad",
    "linea_hoja_ruta",
    "actividad",
    "total_proyectos_que_cubren",
    "total_proyectos_parciales",
    "proyectos_que_cubren",
    "proyectos_parciales",
    "estado_cobertura",
]

RELATION_STATES = {"Cubre", "Cubre parcialmente", "No cubre"}
COVERAGE_STATES = {"Cubierta", "Parcialmente cubierta", "Sin cobertura"}


def normalize_roadmap(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "id_actividad" not in df.columns:
        df.insert(0, "id_actividad", [f"A{i:02d}" for i in range(1, len(df) + 1)])

    for column in ROADMAP_COLUMNS:
        if column not in df.columns:
            df[column] = "No especificado"

    df = df[ROADMAP_COLUMNS].copy()
    for column in ROADMAP_COLUMNS:
        df[column] = df[column].fillna("No especificado").astype(str).str.strip()

    missing_ids = df["id_actividad"].eq("") | df["id_actividad"].isna()
    if missing_ids.any():
        df.loc[missing_ids, "id_actividad"] = [
            f"A{i:02d}" for i in range(1, missing_ids.sum() + 1)
        ]
    return df


def validate_roadmap(df: pd.DataFrame) -> None:
    missing_columns = set(ROADMAP_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError("hoja_ruta.csv no tiene columnas requeridas: " + ", ".join(sorted(missing_columns)))
    if len(df) != EXPECTED_ACTIVITY_COUNT:
        raise ValueError(f"hoja_ruta.csv debe tener exactamente 29 actividades; recibio {len(df)}.")
    if df["id_actividad"].isna().any() or df["id_actividad"].astype(str).str.strip().eq("").any():
        raise ValueError("id_actividad no puede estar vacio.")
    if df["id_actividad"].duplicated().any():
        duplicated = df.loc[df["id_actividad"].duplicated(), "id_actividad"].astype(str).tolist()
        raise ValueError("id_actividad duplicado: " + ", ".join(duplicated))
    if df["actividad"].isna().any() or df["actividad"].astype(str).str.strip().eq("").any():
        raise ValueError("actividad no puede estar vacia.")


def get_project_table(projects_df: pd.DataFrame) -> pd.DataFrame:
    required = {"codigo_proyecto", "nombre_proyecto"}
    missing = required - set(projects_df.columns)
    if missing:
        raise ValueError("proyectos__raw.csv no tiene columnas requeridas: " + ", ".join(sorted(missing)))
    projects = projects_df[["codigo_proyecto", "nombre_proyecto"]].copy()
    projects["codigo_proyecto"] = projects["codigo_proyecto"].astype(str).str.strip()
    projects["nombre_proyecto"] = projects["nombre_proyecto"].astype(str).str.strip()
    projects = projects.drop_duplicates("codigo_proyecto").sort_values("codigo_proyecto")
    if projects.empty:
        raise ValueError("No hay proyectos para mapear.")
    return projects


def normalize_mapping(df: pd.DataFrame, roadmap_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for column in MAPPING_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[MAPPING_COLUMNS].copy()
    for column in MAPPING_COLUMNS:
        df[column] = df[column].fillna("").astype(str).str.strip()

    state_map = {
        "Cubre totalmente": "Cubre",
        "Cubierta": "Cubre",
        "Parcial": "Cubre parcialmente",
        "Parcialmente cubierta": "Cubre parcialmente",
        "No relacionado": "No cubre",
        "No relacionada": "No cubre",
        "Sin cobertura": "No cubre",
    }
    df["estado_relacion"] = df["estado_relacion"].replace(state_map)

    activity_lookup = roadmap_df.set_index("id_actividad")[["linea_hoja_ruta", "actividad"]]
    for activity_id, row in activity_lookup.iterrows():
        mask = df["id_actividad"] == activity_id
        df.loc[mask, "linea_hoja_ruta"] = row["linea_hoja_ruta"]
        df.loc[mask, "actividad"] = row["actividad"]
    return df


def validate_mapping(df: pd.DataFrame, roadmap_df: pd.DataFrame, projects_df: pd.DataFrame) -> None:
    missing_columns = set(MAPPING_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError("mapeo_generado.csv no tiene columnas requeridas: " + ", ".join(sorted(missing_columns)))

    projects = get_project_table(projects_df)
    project_ids = set(projects["codigo_proyecto"])
    activity_ids = set(roadmap_df["id_actividad"].astype(str))

    invalid_projects = sorted(set(df["codigo_proyecto"]) - project_ids)
    if invalid_projects:
        raise ValueError("Codigos de proyecto invalidos: " + ", ".join(invalid_projects))

    invalid_activities = sorted(set(df["id_actividad"]) - activity_ids)
    if invalid_activities:
        raise ValueError("id_actividad invalidos: " + ", ".join(invalid_activities))

    invalid_states = sorted(set(df["estado_relacion"]) - RELATION_STATES)
    if invalid_states:
        raise ValueError("estado_relacion invalido: " + ", ".join(invalid_states))

    if df["justificacion"].astype(str).str.strip().eq("").any():
        bad = df.loc[df["justificacion"].astype(str).str.strip().eq(""), ["codigo_proyecto", "id_actividad"]]
        pairs = [f"{row.codigo_proyecto}+{row.id_actividad}" for row in bad.itertuples()]
        raise ValueError("Justificacion vacia en pares: " + ", ".join(pairs[:20]))

    duplicated = df.duplicated(subset=["codigo_proyecto", "id_actividad"])
    if duplicated.any():
        bad = df.loc[duplicated, ["codigo_proyecto", "id_actividad"]]
        pairs = [f"{row.codigo_proyecto}+{row.id_actividad}" for row in bad.itertuples()]
        raise ValueError("Pares duplicados codigo_proyecto+id_actividad: " + ", ".join(pairs[:20]))

    expected = pd.MultiIndex.from_product(
        [sorted(project_ids), sorted(activity_ids)],
        names=["codigo_proyecto", "id_actividad"],
    )
    actual = pd.MultiIndex.from_frame(df[["codigo_proyecto", "id_actividad"]])
    missing_pairs = expected.difference(actual)
    extra_pairs = actual.difference(expected)
    if len(missing_pairs) or len(extra_pairs):
        details: list[str] = []
        if len(missing_pairs):
            details.append("faltantes: " + ", ".join(f"{a}+{b}" for a, b in missing_pairs[:20]))
        if len(extra_pairs):
            details.append("extras: " + ", ".join(f"{a}+{b}" for a, b in extra_pairs[:20]))
        raise ValueError("Combinaciones proyecto-actividad invalidas; " + " | ".join(details))

    expected_rows = len(project_ids) * EXPECTED_ACTIVITY_COUNT
    if len(df) != expected_rows:
        raise ValueError(f"mapeo_generado.csv debe tener {expected_rows} filas; recibio {len(df)}.")


def build_coverage_summary(roadmap_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, activity in roadmap_df.iterrows():
        activity_id = activity["id_actividad"]
        activity_map = mapping_df[mapping_df["id_actividad"] == activity_id]
        cover_projects = sorted(activity_map.loc[activity_map["estado_relacion"] == "Cubre", "codigo_proyecto"].unique())
        partial_projects = sorted(
            activity_map.loc[activity_map["estado_relacion"] == "Cubre parcialmente", "codigo_proyecto"].unique()
        )

        if cover_projects:
            estado = "Cubierta"
        elif partial_projects:
            estado = "Parcialmente cubierta"
        else:
            estado = "Sin cobertura"

        rows.append(
            {
                "id_actividad": activity_id,
                "linea_hoja_ruta": activity["linea_hoja_ruta"],
                "actividad": activity["actividad"],
                "total_proyectos_que_cubren": len(cover_projects),
                "total_proyectos_parciales": len(partial_projects),
                "proyectos_que_cubren": "; ".join(cover_projects),
                "proyectos_parciales": "; ".join(partial_projects),
                "estado_cobertura": estado,
            }
        )

    summary = pd.DataFrame(rows, columns=COVERAGE_COLUMNS)
    validate_coverage_summary(summary, roadmap_df)
    return summary


def validate_coverage_summary(summary_df: pd.DataFrame, roadmap_df: pd.DataFrame) -> None:
    missing_columns = set(COVERAGE_COLUMNS) - set(summary_df.columns)
    if missing_columns:
        raise ValueError("cobertura_actividades.csv no tiene columnas requeridas: " + ", ".join(sorted(missing_columns)))
    if len(summary_df) != EXPECTED_ACTIVITY_COUNT:
        raise ValueError("cobertura_actividades.csv debe tener exactamente 29 filas.")
    if set(summary_df["id_actividad"]) != set(roadmap_df["id_actividad"]):
        raise ValueError("cobertura_actividades.csv no contiene exactamente las 29 actividades maestras.")
    invalid_states = sorted(set(summary_df["estado_cobertura"]) - COVERAGE_STATES)
    if invalid_states:
        raise ValueError("estado_cobertura invalido: " + ", ".join(invalid_states))


def build_project_activity_matrix(mapping_df: pd.DataFrame, roadmap_df: pd.DataFrame, projects_df: pd.DataFrame) -> pd.DataFrame:
    projects = get_project_table(projects_df)
    project_labels = {
        row.codigo_proyecto: f"{row.codigo_proyecto} - {row.nombre_proyecto}"
        for row in projects.itertuples()
    }
    activity_labels = {
        row.id_actividad: f"{row.id_actividad} - {row.actividad}"
        for row in roadmap_df.itertuples()
    }
    matrix = mapping_df.copy()
    matrix["proyecto"] = matrix["codigo_proyecto"].map(project_labels)
    matrix["actividad_label"] = matrix["id_actividad"].map(activity_labels)
    pivot = matrix.pivot(index="proyecto", columns="actividad_label", values="estado_relacion")
    ordered_rows = [project_labels[code] for code in projects["codigo_proyecto"]]
    ordered_columns = [activity_labels[activity_id] for activity_id in roadmap_df["id_actividad"]]
    return pivot.reindex(index=ordered_rows, columns=ordered_columns)


def save_validated_roadmap(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    normalized = normalize_roadmap(df)
    validate_roadmap(normalized)
    save_csv_atomic(normalized, path)
    return normalized


def save_validated_mapping(df: pd.DataFrame, roadmap_df: pd.DataFrame, projects_df: pd.DataFrame, path: Path) -> pd.DataFrame:
    normalized = normalize_mapping(df, roadmap_df)
    validate_mapping(normalized, roadmap_df, projects_df)
    normalized = normalized.sort_values(["codigo_proyecto", "id_actividad"]).reset_index(drop=True)
    save_csv_atomic(normalized, path)
    return normalized


def save_coverage_summary(roadmap_df: pd.DataFrame, mapping_df: pd.DataFrame, path: Path) -> pd.DataFrame:
    summary = build_coverage_summary(roadmap_df, mapping_df)
    save_csv_atomic(summary, path)
    return summary
