from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_roadmap_llm import main as extract_roadmap_main
from scripts.map_projects_llm import main as map_projects_main
from src import config


def main() -> None:
    try:
        print("Pipeline iniciado.")
        print("Paso 1/2: extraccion de hoja de ruta.")
        extract_roadmap_main()

        print("Paso 2/2: mapeo de proyectos.")
        map_projects_main()

        missing_outputs = [
            str(path.relative_to(config.BASE_DIR))
            for path in (
                config.HOJA_RUTA_CSV,
                config.MAPEO_GENERADO_CSV,
                config.COBERTURA_ACTIVIDADES_CSV,
            )
            if not path.exists()
        ]
        if missing_outputs:
            raise FileNotFoundError(
                "No se generaron los archivos esperados: " + ", ".join(missing_outputs)
            )

        print("Pipeline finalizado correctamente.")
    except SystemExit as exc:
        raise exc
    except Exception as exc:
        print(f"ERROR - {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
