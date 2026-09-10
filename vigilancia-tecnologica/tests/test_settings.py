"""Pruebas para la capa pasiva de settings."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.core import settings as settings_module
from app.core.settings import Settings, load_settings, resolve_project_path


def test_project_root_points_to_project_directory() -> None:
    assert settings_module.PROJECT_ROOT == Path(__file__).resolve().parents[1]
    assert (settings_module.PROJECT_ROOT / "app" / "core" / "settings.py").is_file()
    assert (settings_module.PROJECT_ROOT / "requirements.txt").is_file()


def test_default_values_are_loaded_without_real_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES", raising=False)
    monkeypatch.delenv("SUPABASE_STORAGE_ALLOWED_MIME_TYPES", raising=False)

    settings = load_settings(project_root=tmp_path, env_file=tmp_path / ".env")

    assert isinstance(settings, Settings)
    assert settings.project_root == tmp_path.resolve()
    assert settings.data_dir == (tmp_path / "../Vigilanciatecnologica_data").resolve()
    assert settings.output_dir == (tmp_path / "outputs").resolve()
    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == ""
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_max_output_tokens == 65_536
    assert settings.openai_api_key == ""
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.supabase_url == ""
    assert settings.supabase_key == ""
    assert settings.supabase_service_role_key == ""
    assert settings.supabase_backend_key == ""
    assert settings.supabase_storage_bucket == "source-documents"
    assert settings.storage_file_size_limit_bytes == 52_428_800
    assert settings.storage_allowed_mime_types == (
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_settings_are_immutable(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, env_file=tmp_path / ".env", environ={})

    with pytest.raises(FrozenInstanceError):
        settings.llm_provider = "openai"  # type: ignore[misc]


def test_relative_paths_are_resolved_from_project_root(tmp_path: Path) -> None:
    environ = {
        "DATA_DIR": "local_data",
        "OUTPUT_DIR": "custom_outputs",
    }

    settings = load_settings(
        project_root=tmp_path, env_file=tmp_path / ".env", environ=environ
    )

    assert resolve_project_path("local_data", tmp_path) == (tmp_path / "local_data").resolve()
    assert settings.data_dir == (tmp_path / "local_data").resolve()
    assert settings.output_dir == (tmp_path / "custom_outputs").resolve()
    assert settings.extracted_text_dir == settings.output_dir / "extracted_text"
    assert settings.structured_data_dir == settings.output_dir / "structured_data"
    assert settings.figures_dir == settings.output_dir / "figures"
    assert settings.logs_dir == settings.output_dir / "logs"


def test_absolute_paths_are_preserved(tmp_path: Path) -> None:
    data_dir = tmp_path / "absolute_data"
    output_dir = tmp_path / "absolute_outputs"

    settings = load_settings(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        environ={
            "DATA_DIR": str(data_dir),
            "OUTPUT_DIR": str(output_dir),
        },
    )

    assert settings.data_dir == data_dir.resolve()
    assert settings.output_dir == output_dir.resolve()


def test_supabase_variables_are_loaded(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "test-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-key",
            "SUPABASE_STORAGE_BUCKET": "custom-documents",
            "SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES": "100",
            "SUPABASE_STORAGE_ALLOWED_MIME_TYPES": "application/pdf,text/csv",
        },
    )

    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_key == "test-key"
    assert settings.supabase_service_role_key == "service-key"
    assert settings.supabase_backend_key == "service-key"
    assert settings.supabase_storage_bucket == "custom-documents"
    assert settings.storage_file_size_limit_bytes == 100
    assert settings.storage_allowed_mime_types == ("application/pdf", "text/csv")


def test_gemini_max_output_tokens_is_loaded(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        environ={"GEMINI_MAX_OUTPUT_TOKENS": "32768"},
    )

    assert settings.gemini_max_output_tokens == 32_768


def test_supabase_backend_key_falls_back_to_public_key(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
        },
    )

    assert settings.supabase_backend_key == "anon-key"


def test_source_document_storage_path_is_canonical(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, env_file=tmp_path / ".env", environ={})

    path = settings.source_document_storage_path(
        source_type="institutional plan",
        document_id="doc 123",
        file_name="../PMGE Agenda.xlsx",
    )

    assert path == "institutional-plan/doc-123/PMGE-Agenda.xlsx"


def test_env_file_values_are_loaded_from_isolated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "LLM_PROVIDER=openai\nGEMINI_MODEL=gemini-test\n", encoding="utf-8"
    )

    settings = load_settings(project_root=tmp_path, env_file=env_file)

    assert settings.llm_provider == "openai"
    assert settings.gemini_model == "gemini-test"


def test_load_settings_does_not_create_output_directories(tmp_path: Path) -> None:
    output_dir = tmp_path / "not_created_outputs"

    settings = load_settings(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        environ={"OUTPUT_DIR": "not_created_outputs"},
    )

    assert settings.output_dir == output_dir.resolve()
    assert not output_dir.exists()
    assert not settings.extracted_text_dir.exists()
    assert not settings.structured_data_dir.exists()
    assert not settings.figures_dir.exists()
    assert not settings.logs_dir.exists()
