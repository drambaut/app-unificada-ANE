"""Capa de compatibilidad para la configuracion legacy del MVP."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import load_settings


_settings = load_settings()

PROJECT_ROOT = _settings.project_root
DATA_DIR = _settings.data_dir
OUTPUT_DIR = _settings.output_dir
EXTRACTED_TEXT_DIR = _settings.extracted_text_dir
STRUCTURED_DATA_DIR = _settings.structured_data_dir
FIGURES_DIR = _settings.figures_dir
LOGS_DIR = _settings.logs_dir

LLM_PROVIDER = _settings.llm_provider
GEMINI_API_KEY = _settings.gemini_api_key
GEMINI_MODEL = _settings.gemini_model
OPENAI_API_KEY = _settings.openai_api_key
OPENAI_MODEL = _settings.openai_model
SUPABASE_URL = _settings.supabase_url
SUPABASE_KEY = _settings.supabase_key
SUPABASE_SERVICE_ROLE_KEY = _settings.supabase_service_role_key
SUPABASE_STORAGE_BUCKET = _settings.supabase_storage_bucket
SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES = _settings.storage_file_size_limit_bytes
SUPABASE_STORAGE_ALLOWED_MIME_TYPES = _settings.storage_allowed_mime_types


def ensure_legacy_directories() -> None:
    """Crea los directorios esperados por el pipeline actual basado en archivos."""
    for directory in (
        OUTPUT_DIR,
        EXTRACTED_TEXT_DIR,
        STRUCTURED_DATA_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)


ensure_legacy_directories()
