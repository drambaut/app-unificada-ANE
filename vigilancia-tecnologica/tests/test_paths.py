"""Pruebas basicas para la configuracion de rutas."""

from pathlib import Path

import pytest

import app.config as config
from app.config import (
    DATA_DIR,
    EXTRACTED_TEXT_DIR,
    FIGURES_DIR,
    LOGS_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    STRUCTURED_DATA_DIR,
    SUPABASE_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_STORAGE_ALLOWED_MIME_TYPES,
    SUPABASE_STORAGE_BUCKET,
    SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES,
    SUPABASE_URL,
)
from app.core.settings import load_settings


def test_configured_paths_are_path_objects() -> None:
    paths = (
        PROJECT_ROOT,
        DATA_DIR,
        OUTPUT_DIR,
        EXTRACTED_TEXT_DIR,
        STRUCTURED_DATA_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    )
    assert all(isinstance(path, Path) for path in paths)


def test_output_directories_exist() -> None:
    output_directories = (
        OUTPUT_DIR,
        EXTRACTED_TEXT_DIR,
        STRUCTURED_DATA_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    )
    assert all(directory.is_dir() for directory in output_directories)


def test_legacy_config_constants_match_core_settings() -> None:
    settings = load_settings()

    assert PROJECT_ROOT == settings.project_root
    assert DATA_DIR == settings.data_dir
    assert OUTPUT_DIR == settings.output_dir
    assert EXTRACTED_TEXT_DIR == settings.extracted_text_dir
    assert STRUCTURED_DATA_DIR == settings.structured_data_dir
    assert FIGURES_DIR == settings.figures_dir
    assert LOGS_DIR == settings.logs_dir
    assert SUPABASE_URL == settings.supabase_url
    assert SUPABASE_KEY == settings.supabase_key
    assert SUPABASE_SERVICE_ROLE_KEY == settings.supabase_service_role_key
    assert SUPABASE_STORAGE_BUCKET == settings.supabase_storage_bucket
    assert (
        SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES
        == settings.storage_file_size_limit_bytes
    )
    assert SUPABASE_STORAGE_ALLOWED_MIME_TYPES == settings.storage_allowed_mime_types


def test_ensure_legacy_directories_creates_expected_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "outputs"
    extracted_text_dir = output_dir / "extracted_text"
    structured_data_dir = output_dir / "structured_data"
    figures_dir = output_dir / "figures"
    logs_dir = output_dir / "logs"

    monkeypatch.setattr(config, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(config, "EXTRACTED_TEXT_DIR", extracted_text_dir)
    monkeypatch.setattr(config, "STRUCTURED_DATA_DIR", structured_data_dir)
    monkeypatch.setattr(config, "FIGURES_DIR", figures_dir)
    monkeypatch.setattr(config, "LOGS_DIR", logs_dir)

    config.ensure_legacy_directories()

    assert output_dir.is_dir()
    assert extracted_text_dir.is_dir()
    assert structured_data_dir.is_dir()
    assert figures_dir.is_dir()
    assert logs_dir.is_dir()
