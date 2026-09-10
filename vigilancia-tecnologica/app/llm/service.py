"""Servicio de extraccion estructurada con prompts versionados."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.document_extraction import DOCUMENT_EXTRACTION_SCHEMA
from app.contracts.institutional_plan import INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA
from app.contracts.policy_matrix import POLICY_MATRIX_EXTRACTION_SCHEMA
from app.contracts.regulatory_intelligence import REGULATORY_INTELLIGENCE_SCHEMA
from app.contracts.strategic_assessment import STRATEGIC_ASSESSMENT_SCHEMA
from app.contracts.thematic_landscape import THEMATIC_LANDSCAPE_SCHEMA
from app.contracts.validation import (
    validate_document_extraction,
    validate_institutional_plan_extraction,
    validate_policy_matrix_extraction,
    validate_regulatory_intelligence,
    validate_strategic_assessment,
    validate_thematic_landscape,
)
from app.llm.base import LLMClient, LLMInput
from app.llm.errors import InvalidContractError
from app.llm.gemini_client import GeminiStructuredClient
from app.prompting import load_prompt


SCHEMA_BY_CONTRACT: dict[str, dict[str, Any]] = {
    "DocumentExtraction": DOCUMENT_EXTRACTION_SCHEMA,
    "InstitutionalPlanExtraction": INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
    "PolicyMatrixExtraction": POLICY_MATRIX_EXTRACTION_SCHEMA,
    "ThematicLandscape": THEMATIC_LANDSCAPE_SCHEMA,
    "RegulatoryIntelligence": REGULATORY_INTELLIGENCE_SCHEMA,
    "StrategicAssessment": STRATEGIC_ASSESSMENT_SCHEMA,
}

VALIDATOR_BY_CONTRACT = {
    "DocumentExtraction": validate_document_extraction,
    "InstitutionalPlanExtraction": validate_institutional_plan_extraction,
    "PolicyMatrixExtraction": validate_policy_matrix_extraction,
    "ThematicLandscape": validate_thematic_landscape,
    "RegulatoryIntelligence": validate_regulatory_intelligence,
    "StrategicAssessment": validate_strategic_assessment,
}


@dataclass(frozen=True)
class ExtractionResult:
    payload: dict[str, Any]
    prompt_id: str
    prompt_version: str
    contract_name: str
    model_name: str


class StructuredExtractionService:
    """Orquesta prompt, schema, cliente LLM y validacion local."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or GeminiStructuredClient()

    def extract(
        self,
        *,
        prompt_id: str,
        version: str,
        input_data: LLMInput | str | None = None,
        content: str | None = None,
    ) -> ExtractionResult:
        """Ejecuta extraccion.

        Compatibilidad transitoria: content o input_data=str se convierten a LLMInput.
        """
        spec, prompt = load_prompt(prompt_id, version)
        schema = SCHEMA_BY_CONTRACT.get(spec.contract)
        validator = VALIDATOR_BY_CONTRACT.get(spec.contract)
        if schema is None or validator is None:
            raise InvalidContractError(f"Contrato no soportado: {spec.contract}")

        normalized_input = self._normalize_input(input_data, content)
        payload = self._client.generate_json(
            prompt=prompt,
            input_data=normalized_input,
            response_schema=schema,
        )
        validated = validator(_normalize_provider_payload(payload, schema))
        return ExtractionResult(
            payload=dict(validated),
            prompt_id=spec.prompt_id,
            prompt_version=spec.version,
            contract_name=spec.contract,
            model_name=self._client.model_name,
        )

    def _normalize_input(
        self, input_data: LLMInput | str | None, content: str | None
    ) -> LLMInput:
        if isinstance(input_data, LLMInput):
            return input_data
        if isinstance(input_data, str):
            return LLMInput(text=input_data)
        if content is not None:
            return LLMInput(text=content)
        return LLMInput()


def _normalize_provider_payload(value, schema: dict[str, Any] | None = None):
    """Ajustes defensivos para salidas LLM antes de validar contratos."""
    if schema is not None:
        return _normalize_with_schema(value, schema)
    if isinstance(value, dict):
        normalized = {}
        for key, child in value.items():
            if key == "quote" and isinstance(child, str) and len(child) > 500:
                normalized[key] = child[:500].rstrip()
            else:
                normalized[key] = _normalize_provider_payload(child)
        return normalized
    if isinstance(value, list):
        return [_normalize_provider_payload(item) for item in value]
    return value


def _normalize_with_schema(value, schema: dict[str, Any]):
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), None)
    if schema_type == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            child_schema = properties.get(key, {})
            normalized_child = _normalize_with_schema(child, child_schema)
            if (
                key not in required
                and normalized_child == ""
                and child_schema.get("type") == "string"
                and child_schema.get("minLength", 0) >= 1
            ):
                # Gemini a veces incluye un campo opcional como cadena vacia en
                # vez de omitirlo; se descarta para no romper minLength.
                continue
            normalized[key] = normalized_child
        return normalized
    if schema_type == "array" and isinstance(value, list):
        item_schema = schema.get("items", {})
        normalized = [_normalize_with_schema(item, item_schema) for item in value]
        max_items = schema.get("maxItems")
        if isinstance(max_items, int):
            normalized = normalized[:max_items]
        return normalized
    if schema_type == "string" and isinstance(value, str):
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            return value[:max_length].rstrip()
    return value
