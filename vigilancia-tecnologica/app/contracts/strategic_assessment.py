"""Contrato para valoracion estrategica transversal."""

from app.contracts.common import CONFIDENCE, EVIDENCE_IDS, TEMPORARY_ID, array_of

LEVEL_VALUES = ["Alta", "Media", "Baja"]
ALIGNMENT_TYPE_VALUES = ["strong", "partial", "weak", "none", "tension"]
ID_LIST = {"type": "array", "items": {"type": "string", "minLength": 1}}
DIMENSION_VALUE = {"type": "number", "minimum": 0, "maximum": 5}
SHORT_TEXT = {"type": "string", "maxLength": 700}

IMPORTANCE_DIMENSIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "ane_relevance",
        "magnitude",
        "urgency",
        "evidence_strength",
        "institutional_scope",
    ],
    "properties": {
        "ane_relevance": DIMENSION_VALUE,
        "magnitude": DIMENSION_VALUE,
        "urgency": DIMENSION_VALUE,
        "evidence_strength": DIMENSION_VALUE,
        "institutional_scope": DIMENSION_VALUE,
    },
}

OPPORTUNITY_DIMENSIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "policy_gap",
        "institutional_relevance",
        "actionability",
        "evidence_maturity",
        "timing",
    ],
    "properties": {
        "policy_gap": DIMENSION_VALUE,
        "institutional_relevance": DIMENSION_VALUE,
        "actionability": DIMENSION_VALUE,
        "evidence_maturity": DIMENSION_VALUE,
        "timing": DIMENSION_VALUE,
    },
}

ALIGNMENT_DIMENSIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "objective_match",
        "activity_match",
        "deliverable_match",
        "temporal_match",
        "evidence_strength",
    ],
    "properties": {
        "objective_match": DIMENSION_VALUE,
        "activity_match": DIMENSION_VALUE,
        "deliverable_match": DIMENSION_VALUE,
        "temporal_match": DIMENSION_VALUE,
        "evidence_strength": DIMENSION_VALUE,
    },
}

IMPORTANCE_ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "subject_type",
        "subject_id",
        "dimensions",
        "level",
        "rationale",
        "evidence_ids",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "subject_type": {"type": "string"},
        "subject_id": {"type": "string", "minLength": 1},
        "dimensions": IMPORTANCE_DIMENSIONS_SCHEMA,
        "level": {"type": "string", "enum": LEVEL_VALUES},
        "rationale": SHORT_TEXT,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
    },
}

OPPORTUNITY_ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "theme_id",
        "policy_activity_ids",
        "dimensions",
        "level",
        "rationale",
        "suggested_action",
        "evidence_ids",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "theme_id": {"type": "string", "minLength": 1},
        "policy_activity_ids": ID_LIST,
        "dimensions": OPPORTUNITY_DIMENSIONS_SCHEMA,
        "level": {"type": "string", "enum": LEVEL_VALUES},
        "rationale": SHORT_TEXT,
        "suggested_action": SHORT_TEXT,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
    },
}

ALIGNMENT_ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "theme_id",
        "pmge_project_ids",
        "dimensions",
        "level",
        "rationale",
        "alignment_type",
        "evidence_ids",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "theme_id": {"type": "string", "minLength": 1},
        "pmge_project_ids": ID_LIST,
        "dimensions": ALIGNMENT_DIMENSIONS_SCHEMA,
        "level": {"type": "string", "enum": LEVEL_VALUES},
        "rationale": SHORT_TEXT,
        "alignment_type": {"type": "string", "enum": ALIGNMENT_TYPE_VALUES},
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
    },
}

STRATEGIC_ASSESSMENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "StrategicAssessment",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "importance_assessments",
        "opportunity_assessments",
        "alignment_assessments",
    ],
    "properties": {
        "importance_assessments": array_of(
            IMPORTANCE_ASSESSMENT_SCHEMA, min_items=0, max_items=5
        ),
        "opportunity_assessments": array_of(
            OPPORTUNITY_ASSESSMENT_SCHEMA, min_items=0, max_items=5
        ),
        "alignment_assessments": array_of(
            ALIGNMENT_ASSESSMENT_SCHEMA, min_items=0, max_items=5
        ),
    },
}
