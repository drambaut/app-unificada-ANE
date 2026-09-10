"""Configuracion pasiva de la aplicacion.

Este modulo introduce una capa de settings para la migracion a monolito
modular. Importarlo no crea directorios ni abre conexiones externas.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_BUCKET = "source-documents"
DEFAULT_STORAGE_FILE_SIZE_LIMIT_BYTES = 52_428_800
DEFAULT_STORAGE_ALLOWED_MIME_TYPES = (
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 65_536


@dataclass(frozen=True)
class Settings:
    """Configuracion inmutable leida desde entorno y archivo .env."""

    project_root: Path
    data_dir: Path
    output_dir: Path
    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    gemini_max_output_tokens: int
    openai_api_key: str
    openai_model: str
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    supabase_storage_bucket: str
    storage_file_size_limit_bytes: int
    storage_allowed_mime_types: tuple[str, ...]

    @property
    def supabase_backend_key(self) -> str:
        """Llave para procesos backend: service role si existe, anon/public si no."""
        return self.supabase_service_role_key or self.supabase_key

    @property
    def extracted_text_dir(self) -> Path:
        return self.output_dir / "extracted_text"

    @property
    def structured_data_dir(self) -> Path:
        return self.output_dir / "structured_data"

    @property
    def figures_dir(self) -> Path:
        return self.output_dir / "figures"

    @property
    def logs_dir(self) -> Path:
        return self.output_dir / "logs"

    def source_document_storage_path(
        self, *, source_type: str, document_id: str, file_name: str
    ) -> str:
        """Ruta canonica para originales en Supabase Storage."""
        return "/".join(
            (
                _safe_storage_segment(source_type),
                _safe_storage_segment(document_id),
                _safe_storage_filename(file_name),
            )
        )


def resolve_project_path(value: str, project_root: Path = PROJECT_ROOT) -> Path:
    """Resuelve rutas relativas contra la raiz del proyecto."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def load_settings(
    *,
    project_root: Path = PROJECT_ROOT,
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Carga settings sin producir efectos secundarios de infraestructura."""
    env_path = env_file if env_file is not None else project_root / ".env"
    load_dotenv(env_path, override=False)
    source = environ if environ is not None else os.environ

    return Settings(
        project_root=project_root.resolve(),
        data_dir=resolve_project_path(
            source.get("DATA_DIR", "../Vigilanciatecnologica_data"), project_root
        ),
        output_dir=resolve_project_path(source.get("OUTPUT_DIR", "outputs"), project_root),
        llm_provider=source.get("LLM_PROVIDER", "gemini"),
        gemini_api_key=source.get("GEMINI_API_KEY", ""),
        gemini_model=source.get("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_max_output_tokens=int(
            source.get(
                "GEMINI_MAX_OUTPUT_TOKENS", str(DEFAULT_GEMINI_MAX_OUTPUT_TOKENS)
            )
        ),
        openai_api_key=source.get("OPENAI_API_KEY", ""),
        openai_model=source.get("OPENAI_MODEL", "gpt-4o-mini"),
        supabase_url=source.get("SUPABASE_URL", ""),
        supabase_key=source.get("SUPABASE_KEY", ""),
        supabase_service_role_key=source.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_storage_bucket=source.get(
            "SUPABASE_STORAGE_BUCKET", DEFAULT_STORAGE_BUCKET
        ),
        storage_file_size_limit_bytes=int(
            source.get(
                "SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES",
                str(DEFAULT_STORAGE_FILE_SIZE_LIMIT_BYTES),
            )
        ),
        storage_allowed_mime_types=_split_csv(
            source.get(
                "SUPABASE_STORAGE_ALLOWED_MIME_TYPES",
                ",".join(DEFAULT_STORAGE_ALLOWED_MIME_TYPES),
            )
        ),
    )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _safe_storage_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.=-]+", "-", value.strip())
    cleaned = cleaned.strip(".-")
    if not cleaned:
        raise ValueError("Los segmentos de ruta de Storage no pueden estar vacios.")
    return cleaned


def _safe_storage_filename(value: str) -> str:
    name = Path(value).name
    return _safe_storage_segment(name)
