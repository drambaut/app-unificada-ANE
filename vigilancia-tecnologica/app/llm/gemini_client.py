"""Cliente Gemini para respuestas JSON con schema."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from app.core.settings import Settings, load_settings
from app.llm.base import LLMInput
from app.llm.errors import (
    EmptyLLMResponseError,
    InvalidLLMJSONError,
    LLMProviderError,
    MissingConfigurationError,
)


class GeminiStructuredClient:
    """Encapsula google-genai y crea el cliente solo al ejecutar solicitudes."""

    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client_factory = client_factory
        self._client: Any | None = None

    @property
    def model_name(self) -> str:
        return self._settings.gemini_model

    def _get_client(self) -> Any:
        if not self._settings.gemini_api_key.strip():
            raise MissingConfigurationError("GEMINI_API_KEY no esta configurada.")
        if self._client is None:
            if self._client_factory is None:
                from google import genai

                self._client_factory = genai.Client
            self._client = self._client_factory(api_key=self._settings.gemini_api_key)
        return self._client

    def generate_json(
        self,
        *,
        prompt: str,
        input_data: LLMInput,
        response_schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        last_error: json.JSONDecodeError | None = None
        for attempt, attempt_prompt in enumerate(_retry_prompts(prompt), start=1):
            response = self._generate_content(
                prompt=attempt_prompt,
                input_data=input_data,
                response_schema=response_schema,
            )
            raw_text = getattr(response, "text", None)
            if not raw_text or not str(raw_text).strip():
                raise EmptyLLMResponseError("Gemini devolvio una respuesta vacia.")

            try:
                parsed = json.loads(str(raw_text))
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt == 1:
                    continue
                raise InvalidLLMJSONError(
                    f"Gemini devolvio JSON invalido: {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise InvalidLLMJSONError(
                    "Gemini devolvio JSON valido pero no un objeto."
                )
            return parsed
        raise InvalidLLMJSONError(f"Gemini devolvio JSON invalido: {last_error}")

    def _generate_content(
        self,
        *,
        prompt: str,
        input_data: LLMInput,
        response_schema: Mapping[str, Any],
    ) -> Any:
        try:
            from google.genai import types

            return self._get_client().models.generate_content(
                model=self._settings.gemini_model,
                contents=self._build_contents(types, prompt, input_data),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=_provider_schema(response_schema),
                    temperature=0.1,
                    max_output_tokens=self._settings.gemini_max_output_tokens,
                ),
            )
        except MissingConfigurationError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Error del proveedor Gemini: {exc}") from exc

    def _build_contents(self, types: Any, prompt: str, input_data: LLMInput) -> list[Any]:
        text = self._build_text_part(prompt, input_data)
        parts = [types.Part.from_text(text=text)]
        if input_data.file_bytes is not None:
            parts.append(
                types.Part.from_bytes(
                    data=input_data.file_bytes,
                    mime_type=input_data.mime_type or "application/octet-stream",
                )
            )
        return parts

    def _build_text_part(self, prompt: str, input_data: LLMInput) -> str:
        metadata = "\n".join(
            f"- {key}: {value}" for key, value in sorted(input_data.metadata.items())
        )
        sections = [prompt.rstrip()]
        if metadata:
            sections.append(f"METADATOS:\n{metadata}")
        if input_data.file_name:
            sections.append(f"ARCHIVO: {input_data.file_name}")
        if input_data.text.strip():
            sections.append(f"CONTENIDO A ANALIZAR:\n{input_data.text}")
        return "\n\n".join(sections)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de textos usando text-embedding-004."""
        if not texts:
            return []
        try:
            response = self._get_client().models.embed_content(
                model="text-embedding-004",
                contents=texts,
            )
            embeddings = getattr(response, "embeddings", [])
            return [list(e.values) for e in embeddings]
        except Exception as exc:
            raise LLMProviderError(f"Error generando embeddings: {exc}") from exc


def _retry_prompts(prompt: str) -> tuple[str, str]:
    compact_retry = (
        f"{prompt.rstrip()}\n\n"
        "REINTENTO POR JSON INVALIDO O TRUNCADO:\n"
        "- Devuelve una version mucho mas corta.\n"
        "- Prioriza maximo 2 elementos por lista principal.\n"
        "- Usa frases breves y evita parrafos largos.\n"
        "- Conserva estrictamente el JSON Schema recibido.\n"
        "- Devuelve solo JSON valido y completo."
    )
    return (prompt, compact_retry)


def _provider_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Quita restricciones que hacen inestable el response_schema de Gemini."""
    return _strip_provider_constraints(dict(schema))


def _strip_provider_constraints(value: Any, *, parent_key: str | None = None) -> Any:
    unsupported = {
        "$schema",
        "description",
        "maxItems",
        "maxLength",
        "minLength",
        "minimum",
        "maximum",
    }
    if isinstance(value, dict):
        return {
            key: _strip_provider_constraints(child, parent_key=key)
            for key, child in value.items()
            if parent_key == "properties" or key not in unsupported
        }
    if isinstance(value, list):
        return [_strip_provider_constraints(child) for child in value]
    return value
