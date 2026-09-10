"""Interfaces base para clientes LLM estructurados."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMInput:
    """Entrada multimodal o textual para un cliente LLM."""

    text: str = ""
    file_bytes: bytes | None = None
    mime_type: str | None = None
    file_name: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.file_bytes is not None and (not self.mime_type or not self.file_name):
            raise ValueError("mime_type y file_name son obligatorios con file_bytes.")


class LLMClient(Protocol):
    """Cliente capaz de devolver JSON estructurado."""

    @property
    def model_name(self) -> str:
        """Nombre del modelo usado por el cliente."""

    def generate_json(
        self,
        *,
        prompt: str,
        input_data: LLMInput,
        response_schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Ejecuta una extraccion y devuelve un diccionario JSON."""
