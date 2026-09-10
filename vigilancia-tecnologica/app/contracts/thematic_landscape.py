"""Contrato para analisis transversal de paisaje tematico."""

from app.contracts.common import (
    CONFIDENCE,
    EVIDENCE_IDS,
    EXTRACTION_BASIS,
    TEMPORARY_ID,
    array_of,
)

CHANGE_ACTION_VALUES = ["create", "retain", "rename", "merge", "split", "retire"]
TREND_DIRECTION_VALUES = ["emerging", "growing", "stable", "declining", "uncertain"]
TIME_HORIZON_VALUES = ["short_term", "medium_term", "long_term", "uncertain"]

ID_LIST = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "maxItems": 8,
}
SHORT_TEXT = {"type": "string", "maxLength": 600}
MEDIUM_TEXT = {"type": "string", "maxLength": 1200}
OPEN_TEXT_LIST = {
    "type": "array",
    "items": {"type": "string", "maxLength": 160},
    "maxItems": 6,
}

THEME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "name",
        "definition",
        "scope",
        "subthemes",
        "technologies",
        "frequency_bands",
        "countries_regions",
        "organizations",
        "finding_ids",
        "evidence_ids",
        "change_action",
        "previous_topic_ids",
        "confidence",
        "extraction_basis",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "name": SHORT_TEXT,
        "definition": SHORT_TEXT,
        "scope": SHORT_TEXT,
        "subthemes": OPEN_TEXT_LIST,
        "technologies": OPEN_TEXT_LIST,
        "frequency_bands": OPEN_TEXT_LIST,
        "countries_regions": OPEN_TEXT_LIST,
        "organizations": OPEN_TEXT_LIST,
        "finding_ids": ID_LIST,
        "evidence_ids": EVIDENCE_IDS,
        "change_action": {"type": "string", "enum": CHANGE_ACTION_VALUES},
        "previous_topic_ids": ID_LIST,
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
    },
}

TREND_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "name",
        "description",
        "related_theme_temporary_ids",
        "direction",
        "time_horizon",
        "countries_regions",
        "organizations",
        "finding_ids",
        "evidence_ids",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "name": SHORT_TEXT,
        "description": SHORT_TEXT,
        "related_theme_temporary_ids": ID_LIST,
        "direction": {"type": "string", "enum": TREND_DIRECTION_VALUES},
        "time_horizon": {"type": "string", "enum": TIME_HORIZON_VALUES},
        "first_observed_date": {"type": ["string", "null"]},
        "latest_observed_date": {"type": ["string", "null"]},
        "countries_regions": OPEN_TEXT_LIST,
        "organizations": OPEN_TEXT_LIST,
        "finding_ids": ID_LIST,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
    },
}

EMERGING_SIGNAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "title",
        "description",
        "novelty_explanation",
        "related_theme_temporary_ids",
        "finding_ids",
        "evidence_ids",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "title": SHORT_TEXT,
        "description": SHORT_TEXT,
        "novelty_explanation": SHORT_TEXT,
        "related_theme_temporary_ids": ID_LIST,
        "finding_ids": ID_LIST,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
    },
}

THEMATIC_LANDSCAPE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ThematicLandscape",
    "type": "object",
    "additionalProperties": False,
    "required": ["corpus_summary", "themes", "trends", "emerging_signals", "evidence_ids"],
    "properties": {
        "corpus_summary": MEDIUM_TEXT,
        "themes": array_of(THEME_SCHEMA, min_items=0, max_items=4),
        "trends": array_of(TREND_SCHEMA, min_items=0, max_items=4),
        "emerging_signals": array_of(EMERGING_SIGNAL_SCHEMA, min_items=0, max_items=3),
        "evidence_ids": EVIDENCE_IDS,
    },
}
