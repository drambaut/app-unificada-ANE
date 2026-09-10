"""Contrato para extraccion de matrices de politicas publicas."""

from app.contracts.common import (
    CONFIDENCE,
    EVIDENCE_IDS,
    EVIDENCE_SCHEMA,
    EXTRACTION_BASIS,
    OPEN_TEXT_LIST,
    TEMPORARY_ID,
    array_of,
)

POLICY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "policy_name",
        "instrument_name",
        "policy_axis",
        "description",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "policy_name": {"type": "string"},
        "instrument_name": {"type": ["string", "null"]},
        "policy_axis": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

POLICY_ACTIVITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "policy_temporary_id",
        "activity_name",
        "activity_description",
        "responsible_area",
        "execution_period",
        "commitments",
        "keywords",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "policy_temporary_id": {"type": ["string", "null"]},
        "activity_name": {"type": "string"},
        "activity_description": {"type": "string"},
        "responsible_area": {"type": ["string", "null"]},
        "execution_period": {"type": ["string", "null"]},
        "commitments": OPEN_TEXT_LIST,
        "keywords": OPEN_TEXT_LIST,
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

POLICY_COMMITMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "policy_activity_temporary_id",
        "commitment_text",
        "responsible_area",
        "period",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "policy_activity_temporary_id": {"type": ["string", "null"]},
        "commitment_text": {"type": "string"},
        "responsible_area": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

POLICY_MATRIX_EXTRACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PolicyMatrixExtraction",
    "type": "object",
    "additionalProperties": False,
    "required": ["policies", "activities", "commitments", "evidence"],
    "properties": {
        "policies": array_of(POLICY_SCHEMA, min_items=0),
        "activities": array_of(POLICY_ACTIVITY_SCHEMA, min_items=0),
        "commitments": array_of(POLICY_COMMITMENT_SCHEMA, min_items=0),
        "evidence": array_of(EVIDENCE_SCHEMA, min_items=0),
    },
}
