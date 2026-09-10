from pathlib import Path

import pandas as pd

from src.coverage_model import (
    MAPPING_COLUMNS,
    ROADMAP_COLUMNS,
    get_project_table,
    save_validated_mapping,
    save_validated_roadmap,
)
from src.gemini_client import generate_text
from src.preprocessing import csv_text_to_dataframe, extract_text_from_pdf


MAX_BATCH_ATTEMPTS = 3
ACTIVITIES_PER_BATCH = 5


def extract_roadmap_from_pdf_with_gemini(
    pdf_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Extrae exactamente 29 actividades del PDF y guarda la tabla maestra validada."""
    pdf_text = extract_text_from_pdf(pdf_path)
    prompt = f"""Eres un asistente experto en estructuracion de documentos institucionales.

Recibiras el texto extraido de un PDF llamado "Estrategia de gestion de datos SGP_VF.pdf".
Tu tarea es extraer exactamente las 29 actividades de la hoja de ruta SGP.

Devuelve SOLO un CSV valido, sin markdown y sin explicacion, con estas columnas:

id_actividad,linea_hoja_ruta,actividad,horizonte,observaciones

Reglas:
1. Extrae exactamente 29 actividades, una fila por actividad.
2. id_actividad debe ser estable, unico y no nulo. Usa A01, A02, ..., A29 en el orden del documento.
3. No resumas varias actividades en una sola.
4. No dividas una actividad salvo que el documento la presente expresamente como actividad diferente.
5. No inventes responsables, horizontes ni informacion ausente.
6. Si horizonte u observaciones no aparecen, escribe "No especificado".
7. Conserva el sentido del texto original.
8. No uses saltos de linea dentro de una celda.
9. Todas las celdas deben estar entre comillas dobles.
10. Si una celda contiene comillas dobles, escapalas duplicandolas.
11. No devuelvas markdown.
12. No agregues texto antes ni despues del CSV.

Texto del PDF:
{pdf_text}
"""
    response_text = generate_text(prompt)
    df = csv_text_to_dataframe(response_text)
    missing_columns = set(ROADMAP_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(
            "Gemini no devolvio la tabla maestra esperada. Faltan columnas: "
            + ", ".join(sorted(missing_columns))
        )
    return save_validated_roadmap(df, output_path)


def map_projects_to_roadmap_with_gemini(
    projects_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    """
    Compara todos los proyectos contra cada actividad en lotes de una actividad.
    El resultado final contiene una fila por cada par codigo_proyecto + id_actividad.
    """
    if projects_df.empty:
        raise ValueError("El DataFrame de proyectos esta vacio.")
    if roadmap_df.empty:
        raise ValueError("El DataFrame de hoja de ruta esta vacio.")

    projects = get_project_table(projects_df)
    project_count = len(projects)
    project_context_columns = [
        column
        for column in [
            "codigo_proyecto",
            "nombre_proyecto",
            "objetivo",
            "alcance",
            "descripcion_general",
            "observaciones",
            "vigencia",
        ]
        if column in projects_df.columns
    ]
    projects_csv = projects_df[project_context_columns].to_csv(index=False)

    batches: list[pd.DataFrame] = []
    for start in range(0, len(roadmap_df), ACTIVITIES_PER_BATCH):
        activity_batch = roadmap_df.iloc[start : start + ACTIVITIES_PER_BATCH].copy()
        activity_csv = activity_batch.to_csv(index=False)
        expected_rows = project_count * len(activity_batch)
        batch_label = ", ".join(activity_batch["id_actividad"].astype(str))
        prompt = _build_mapping_prompt(expected_rows, activity_csv, projects_csv)
        batch_df = _generate_activity_batch(prompt, batch_label, expected_rows)
        batches.append(batch_df)

    combined = pd.concat(batches, ignore_index=True)
    return save_validated_mapping(combined, roadmap_df, projects_df, output_path)


def _build_mapping_prompt(expected_rows: int, activity_csv: str, projects_csv: str) -> str:
    return f"""Eres un asistente experto en planeacion institucional y hojas de ruta.

Debes comparar TODAS las actividades de la Hoja de Ruta SGP recibidas contra TODOS los proyectos recibidos.

Devuelve exactamente {expected_rows} filas: una fila por cada combinacion codigo_proyecto + id_actividad.
No omitas ningun proyecto, no omitas ninguna actividad y no agregues proyectos ni actividades.

Devuelve SOLO un CSV valido, sin markdown ni explicacion, con estas columnas:

codigo_proyecto,nombre_proyecto,id_actividad,linea_hoja_ruta,actividad,estado_relacion,justificacion

Estados permitidos para estado_relacion:
- Cubre
- Cubre parcialmente
- No cubre

Definiciones:
- Cubre: el proposito, alcance o descripcion del proyecto coincide de manera clara y sustancial con lo que busca realizar la actividad.
- Cubre parcialmente: el proyecto se relaciona con la actividad, pero atiende solo una parte o un componente.
- No cubre: el proposito, alcance y descripcion del proyecto no se relacionan de manera suficiente con la actividad.

Reglas:
1. Analiza solo codigo, nombre, objetivo, alcance, descripcion general, observaciones y vigencia del proyecto.
2. No inventes funciones, entregables, resultados ni avance tecnico.
3. No evalues evidencia, confianza, validacion, revision ni decision de vigencia.
4. No uses "Por validar" bajo ninguna circunstancia.
5. Una coincidencia aislada de palabras no es suficiente para afirmar cobertura.
6. La justificacion debe ser una sola frase corta que explique directamente la relacion.
7. La justificacion no debe mencionar evidencia, confianza, validacion, porcentajes ni avance.
8. No uses saltos de linea dentro de una celda.
9. Todas las celdas deben estar entre comillas dobles.
10. Si una celda contiene comillas dobles, escapalas duplicandolas.
11. No agregues texto antes ni despues del CSV.

Actividades:
{activity_csv}

Proyectos:
{projects_csv}
"""


def _generate_activity_batch(prompt: str, batch_label: str, expected_rows: int) -> pd.DataFrame:
    last_error = ""
    last_response = ""

    for attempt in range(1, MAX_BATCH_ATTEMPTS + 1):
        response_text = generate_text(prompt)
        last_response = response_text[:800].replace("\n", " ")

        try:
            batch_df = csv_text_to_dataframe(response_text)
        except Exception as exc:
            last_error = str(exc)
            prompt = _retry_prompt(prompt, batch_label, expected_rows, last_error)
            continue

        missing_columns = set(MAPPING_COLUMNS) - set(batch_df.columns)
        if missing_columns:
            last_error = "Faltan columnas: " + ", ".join(sorted(missing_columns))
            prompt = _retry_prompt(prompt, batch_label, expected_rows, last_error)
            continue

        if len(batch_df) != expected_rows:
            last_error = f"Filas recibidas: {len(batch_df)}; esperadas: {expected_rows}"
            prompt = _retry_prompt(prompt, batch_label, expected_rows, last_error)
            continue

        return batch_df

    raise ValueError(
        f"Gemini no devolvio el lote esperado para {batch_label} despues de "
        f"{MAX_BATCH_ATTEMPTS} intentos. Ultimo error: {last_error}. "
        f"Preview respuesta: {last_response}"
    )


def _retry_prompt(original_prompt: str, batch_label: str, expected_rows: int, error: str) -> str:
    return (
        original_prompt
        + "\n\nLa respuesta anterior fue invalida para el lote "
        + batch_label
        + ". Error detectado: "
        + error
        + "\nDevuelve nuevamente SOLO CSV valido con el encabezado exacto:\n"
        + "codigo_proyecto,nombre_proyecto,id_actividad,linea_hoja_ruta,actividad,estado_relacion,justificacion\n"
        + f"Debe tener exactamente {expected_rows} filas de datos y ninguna explicacion."
    )


def extract_roadmap_from_pdf(pdf_path: Path) -> pd.DataFrame:
    raise NotImplementedError(
        "Usa extract_roadmap_from_pdf_with_gemini(pdf_path, output_path)."
    )


def map_projects_to_roadmap(
    projects_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
) -> pd.DataFrame:
    raise NotImplementedError(
        "Usa map_projects_to_roadmap_with_gemini(projects_df, roadmap_df, output_path)."
    )
