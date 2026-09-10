"""Loader pasivo para prompts versionados."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import PROJECT_ROOT
from app.prompting.registry import PromptSpec, get_prompt_spec


def load_prompt(prompt_id: str, version: str) -> tuple[PromptSpec, str]:
    """Carga el texto de un prompt registrado sin llamar servicios externos."""
    spec = get_prompt_spec(prompt_id, version)
    prompt_path = PROJECT_ROOT / spec.path
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"El prompt '{prompt_id}@{version}' esta registrado, "
            f"pero no existe el archivo: {prompt_path}"
        )
    content = prompt_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"El prompt '{prompt_id}@{version}' esta vacio: {prompt_path}")
    return spec, content
