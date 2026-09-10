from __future__ import annotations

import pathlib
import tempfile
import unittest

import pandas as pd

from src.coverage_model import save_validated_mapping

from tests.test_coverage_model import make_complete_mapping, make_projects, make_roadmap


class DashboardContractTests(unittest.TestCase):
    def test_dashboard_does_not_call_gemini(self) -> None:
        app_text = pathlib.Path("app.py").read_text(encoding="utf-8")
        dashboard_text = pathlib.Path("src/dashboard.py").read_text(encoding="utf-8")
        forbidden = ["generate_text", "GEMINI_API_KEY", "gemini_client", "map_projects_to_roadmap"]
        for term in forbidden:
            self.assertNotIn(term, app_text)
            self.assertNotIn(term, dashboard_text)

    def test_invalid_mapping_does_not_replace_existing_file(self) -> None:
        roadmap = make_roadmap()
        projects = make_projects()
        valid = make_complete_mapping()
        invalid = valid.drop(valid.index[0]).copy()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "mapeo_generado.csv"
            save_validated_mapping(valid, roadmap, projects, path)
            before = path.read_text(encoding="utf-8")

            with self.assertRaises(ValueError):
                save_validated_mapping(invalid, roadmap, projects, path)

            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
