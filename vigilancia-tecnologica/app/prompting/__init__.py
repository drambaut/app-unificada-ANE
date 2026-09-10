"""Carga y registro de prompts versionados."""

from app.prompting.loader import load_prompt
from app.prompting.registry import PROMPT_REGISTRY, PromptSpec, get_prompt_spec

__all__ = ["PROMPT_REGISTRY", "PromptSpec", "get_prompt_spec", "load_prompt"]
