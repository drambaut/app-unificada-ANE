from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env", override=True)

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
DATA_EXPORTS_DIR = BASE_DIR / "data" / "exports"

PROYECTOS_RAW_CSV = DATA_RAW_DIR / "proyectos__raw.csv"
HOJA_RUTA_PDF = DATA_RAW_DIR / "Estrategia de gestion de datos SGP_VF.pdf"

HOJA_RUTA_CSV = DATA_PROCESSED_DIR / "hoja_ruta.csv"
MAPEO_GENERADO_CSV = DATA_PROCESSED_DIR / "mapeo_generado.csv"
MAPEO_VALIDADO_CSV = DATA_PROCESSED_DIR / "mapeo_validado.csv"
COBERTURA_ACTIVIDADES_CSV = DATA_PROCESSED_DIR / "cobertura_actividades.csv"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
