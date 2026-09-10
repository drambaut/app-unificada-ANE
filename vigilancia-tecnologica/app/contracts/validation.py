"""Validacion local de respuestas contra contratos JSON Schema."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.contracts.document_extraction import DOCUMENT_EXTRACTION_SCHEMA
from app.contracts.institutional_plan import INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA
from app.contracts.policy_matrix import POLICY_MATRIX_EXTRACTION_SCHEMA
from app.contracts.regulatory_intelligence import REGULATORY_INTELLIGENCE_SCHEMA
from app.contracts.strategic_assessment import STRATEGIC_ASSESSMENT_SCHEMA
from app.contracts.thematic_landscape import THEMATIC_LANDSCAPE_SCHEMA


class ContractValidationError(ValueError):
    """Error legible para payloads que incumplen un contrato."""

    def __init__(self, contract_name: str, path: str, rule: str, detail: str) -> None:
        self.contract_name = contract_name
        self.path = path
        self.rule = rule
        self.detail = detail
        super().__init__(f"{contract_name}.{path}: {detail} [rule={rule}]")


def _contract_name(schema: Mapping[str, Any]) -> str:
    return str(schema.get("title") or "Contract")


def _format_path(error: ValidationError) -> str:
    path = ""
    for part in error.absolute_path:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path = f"{path}.{part}" if path else str(part)
    return path or "<root>"


def _format_detail(error: ValidationError) -> str:
    if error.validator == "required":
        missing = sorted(set(error.validator_value).difference(error.instance))
        if missing:
            return f"campo obligatorio ausente: {', '.join(repr(item) for item in missing)}"
    if error.validator == "additionalProperties":
        return f"propiedad adicional no permitida: {error.message}"
    return error.message


def validate_contract(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Valida un diccionario contra JSON Schema y devuelve el payload si es valido."""
    contract_name = _contract_name(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        raise ContractValidationError(
            contract_name=contract_name,
            path=_format_path(error),
            rule=str(error.validator),
            detail=_format_detail(error),
        )
    return payload


def validate_document_extraction(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, DOCUMENT_EXTRACTION_SCHEMA)


def validate_institutional_plan_extraction(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA)


def validate_policy_matrix_extraction(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, POLICY_MATRIX_EXTRACTION_SCHEMA)


def validate_thematic_landscape(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, THEMATIC_LANDSCAPE_SCHEMA)


def validate_regulatory_intelligence(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, REGULATORY_INTELLIGENCE_SCHEMA)


def validate_strategic_assessment(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return validate_contract(payload, STRATEGIC_ASSESSMENT_SCHEMA)
