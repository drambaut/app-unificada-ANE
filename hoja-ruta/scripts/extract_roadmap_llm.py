from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.coverage_model import EXPECTED_ACTIVITY_COUNT, ROADMAP_COLUMNS, validate_roadmap
from src.data_loader import load_csv
from src.llm_mapper import extract_roadmap_from_pdf_with_gemini


def validate_columns(output_path: Path) -> None:
    df = load_csv(output_path)
    missing_columns = sorted(set(ROADMAP_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(
            "hoja_ruta.csv no tiene las columnas esperadas: "
            + ", ".join(missing_columns)
        )

    validate_roadmap(df)
    if len(df) != EXPECTED_ACTIVITY_COUNT:
        raise ValueError("La tabla maestra no contiene exactamente 29 actividades.")


def main() -> None:
    try:
        config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        if not config.HOJA_RUTA_PDF.exists():
            raise FileNotFoundError(
                "No se encontro data/raw/Estrategia de gestion de datos SGP_VF.pdf."
            )

        print("Leyendo PDF...")
        print("Enviando texto a Gemini...")
        extract_roadmap_from_pdf_with_gemini(
            config.HOJA_RUTA_PDF,
            config.HOJA_RUTA_CSV,
        )

        print("Guardando hoja_ruta.csv...")
        validate_columns(config.HOJA_RUTA_CSV)
        print("Extraccion finalizada.")
    except Exception as exc:
        print(f"ERROR - {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
