from __future__ import annotations

import unittest

import pandas as pd

from src.dashboard import build_articulation_nodes, build_articulation_view


class DashboardArticulationTests(unittest.TestCase):
    def test_build_articulation_view_builds_hierarchy_from_summary(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "id_actividad": "A07",
                    "linea_hoja_ruta": "Gobernanza de datos",
                    "actividad": "Comite",
                    "estado_cobertura": "Parcialmente cubierta",
                },
                {
                    "id_actividad": "A10",
                    "linea_hoja_ruta": "Gobernanza de datos",
                    "actividad": "Plantillas",
                    "estado_cobertura": "Cubierta",
                },
                {
                    "id_actividad": "A11",
                    "linea_hoja_ruta": "Gobernanza de datos",
                    "actividad": "Seguridad",
                    "estado_cobertura": "Sin cobertura",
                },
                {
                    "id_actividad": "A24",
                    "linea_hoja_ruta": "Optimizacion",
                    "actividad": "Trazabilidad",
                    "estado_cobertura": "Cubierta",
                },
            ]
        )

        articulation = build_articulation_view(summary)

        self.assertEqual(
            list(articulation["actividad_label"]),
            ["A07", "A10", "A11", "A24"],
        )
        self.assertTrue((articulation["estrategia"] == "Estrategia de datos").all())
        self.assertEqual(list(articulation["linea_label"]), ["Gobernanza", "Gobernanza", "Gobernanza", "Optimizacion"])
        self.assertTrue((articulation["peso"] == 1).all())
        self.assertIn("Contribuye de forma directa a la estrategia.", set(articulation["aporte_actual"]))
        self.assertIn("Actividad prevista en la estrategia con cobertura pendiente.", set(articulation["aporte_actual"]))

    def test_build_articulation_nodes_includes_hierarchy_and_interpretation(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "id_actividad": "A07",
                    "linea_hoja_ruta": "Gobernanza de datos",
                    "actividad": "Comite",
                    "estado_cobertura": "Parcialmente cubierta",
                },
                {
                    "id_actividad": "A24",
                    "linea_hoja_ruta": "Optimizacion",
                    "actividad": "Trazabilidad",
                    "estado_cobertura": "Cubierta",
                },
                {
                    "id_actividad": "A20",
                    "linea_hoja_ruta": "Analitica de datos",
                    "actividad": "Contactos",
                    "estado_cobertura": "Sin cobertura",
                },
            ]
        )

        nodes = build_articulation_nodes(summary)

        self.assertIn("estrategia", set(nodes["id"]))
        self.assertIn("linea::Gobernanza", set(nodes["id"]))
        self.assertIn("actividad::A24", set(nodes["id"]))
        activity_node = nodes[nodes["id"] == "actividad::A24"].iloc[0]
        gap_node = nodes[nodes["id"] == "actividad::A20"].iloc[0]
        self.assertEqual(activity_node["interpretation"], "Contribuye")
        self.assertEqual(gap_node["interpretation"], "Requiere fortalecimiento")


if __name__ == "__main__":
    unittest.main()
