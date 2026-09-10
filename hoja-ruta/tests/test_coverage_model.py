from __future__ import annotations

import unittest

import pandas as pd

from src.coverage_model import (
    EXPECTED_ACTIVITY_COUNT,
    MAPPING_COLUMNS,
    build_coverage_summary,
    build_project_activity_matrix,
    normalize_mapping,
    validate_coverage_summary,
    validate_mapping,
    validate_roadmap,
)


def make_roadmap() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id_actividad": [f"A{i:02d}" for i in range(1, EXPECTED_ACTIVITY_COUNT + 1)],
            "linea_hoja_ruta": ["Linea 1"] * EXPECTED_ACTIVITY_COUNT,
            "actividad": [f"Actividad {i}" for i in range(1, EXPECTED_ACTIVITY_COUNT + 1)],
            "horizonte": ["No especificado"] * EXPECTED_ACTIVITY_COUNT,
            "observaciones": ["No especificado"] * EXPECTED_ACTIVITY_COUNT,
        }
    )


def make_projects() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "codigo_proyecto": ["ED01", "ED02"],
            "nombre_proyecto": ["Proyecto uno", "Proyecto dos"],
        }
    )


def make_complete_mapping() -> pd.DataFrame:
    rows = []
    for project in make_projects().itertuples():
        for activity in make_roadmap().itertuples():
            state = "No cubre"
            if project.codigo_proyecto == "ED01" and activity.id_actividad == "A01":
                state = "Cubre"
            elif project.codigo_proyecto == "ED02" and activity.id_actividad == "A02":
                state = "Cubre parcialmente"
            rows.append(
                {
                    "codigo_proyecto": project.codigo_proyecto,
                    "nombre_proyecto": project.nombre_proyecto,
                    "id_actividad": activity.id_actividad,
                    "linea_hoja_ruta": activity.linea_hoja_ruta,
                    "actividad": activity.actividad,
                    "estado_relacion": state,
                    "justificacion": f"{project.codigo_proyecto} frente a {activity.id_actividad}.",
                }
            )
    return pd.DataFrame(rows, columns=MAPPING_COLUMNS)


class CoverageModelTests(unittest.TestCase):
    def test_roadmap_requires_29_unique_activities(self) -> None:
        roadmap = make_roadmap()
        validate_roadmap(roadmap)
        self.assertEqual(roadmap["id_actividad"].nunique(), EXPECTED_ACTIVITY_COUNT)

    def test_mapping_has_project_by_activity_cross_join(self) -> None:
        roadmap = make_roadmap()
        projects = make_projects()
        mapping = normalize_mapping(make_complete_mapping(), roadmap)
        validate_mapping(mapping, roadmap, projects)
        self.assertEqual(len(mapping), len(projects) * EXPECTED_ACTIVITY_COUNT)

    def test_no_duplicate_or_missing_pairs(self) -> None:
        roadmap = make_roadmap()
        projects = make_projects()
        mapping = normalize_mapping(make_complete_mapping(), roadmap)
        self.assertFalse(mapping.duplicated(["codigo_proyecto", "id_actividad"]).any())
        validate_mapping(mapping, roadmap, projects)

    def test_only_three_states_and_no_por_validar(self) -> None:
        mapping = make_complete_mapping()
        self.assertEqual(set(mapping["estado_relacion"]), {"Cubre", "Cubre parcialmente", "No cubre"})
        self.assertNotIn("Por validar", set(mapping["estado_relacion"]))

    def test_no_confidence_or_evidence_columns(self) -> None:
        forbidden = {"nivel_confianza", "evidencia_proyecto", "requiere_validacion", "decision_vigencia"}
        self.assertTrue(forbidden.isdisjoint(set(MAPPING_COLUMNS)))

    def test_python_consolidation_rules(self) -> None:
        roadmap = make_roadmap()
        mapping = normalize_mapping(make_complete_mapping(), roadmap)
        summary = build_coverage_summary(roadmap, mapping)
        validate_coverage_summary(summary, roadmap)
        self.assertEqual(summary.loc[summary["id_actividad"] == "A01", "estado_cobertura"].iloc[0], "Cubierta")
        self.assertEqual(
            summary.loc[summary["id_actividad"] == "A02", "estado_cobertura"].iloc[0],
            "Parcialmente cubierta",
        )
        self.assertEqual(summary.loc[summary["id_actividad"] == "A03", "estado_cobertura"].iloc[0], "Sin cobertura")

    def test_matrix_orientation_and_labels(self) -> None:
        roadmap = make_roadmap()
        projects = make_projects()
        mapping = normalize_mapping(make_complete_mapping(), roadmap)
        matrix = build_project_activity_matrix(mapping, roadmap, projects)
        self.assertEqual(matrix.shape, (2, EXPECTED_ACTIVITY_COUNT))
        self.assertTrue(matrix.index[0].startswith("ED01 - Proyecto uno"))
        self.assertTrue(matrix.columns[0].startswith("A01 - Actividad 1"))

    def test_invalid_state_fails(self) -> None:
        roadmap = make_roadmap()
        projects = make_projects()
        mapping = make_complete_mapping()
        mapping.loc[0, "estado_relacion"] = "Por validar"
        normalized = normalize_mapping(mapping, roadmap)
        with self.assertRaises(ValueError):
            validate_mapping(normalized, roadmap, projects)


if __name__ == "__main__":
    unittest.main()
