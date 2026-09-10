"""Contrato para inteligencia regulatoria transversal."""

from app.contracts.common import (
    CONFIDENCE,
    EVIDENCE_IDS,
    EXTRACTION_BASIS,
    TEMPORARY_ID,
    array_of,
)

RELATIONSHIP_TYPE_VALUES = [
    "covered",
    "partially_covered",
    "gap",
    "complementary",
    "tension",
    "no_direct_relation",
]

ID_LIST = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "maxItems": 8,
}
SHORT_TEXT = {"type": "string", "maxLength": 700}
OPEN_TEXT_LIST = {
    "type": "array",
    "items": {"type": "string", "maxLength": 180},
    "maxItems": 6,
}

REGULATORY_INTELLIGENCE_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "international_situation",
        "regulatory_debate",
        "countries_regions",
        "organizations",
        "agenda_item_ids",
        "relationship_type",
        "coverage_explanation",
        "implications_for_ane",
        "finding_ids",
        "evidence_ids",
        "confidence",
        "extraction_basis",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "theme_id": {"type": "string", "minLength": 1},
        "theme_temporary_id": {"type": "string", "minLength": 1},
        "international_situation": SHORT_TEXT,
        "regulatory_debate": SHORT_TEXT,
        "countries_regions": OPEN_TEXT_LIST,
        "organizations": OPEN_TEXT_LIST,
        "agenda_item_ids": ID_LIST,
        "relationship_type": {"type": "string", "enum": RELATIONSHIP_TYPE_VALUES},
        "coverage_explanation": SHORT_TEXT,
        "implications_for_ane": SHORT_TEXT,
        "finding_ids": ID_LIST,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
    },
}

REGULATORY_INTELLIGENCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "RegulatoryIntelligence",
    "type": "object",
    "additionalProperties": False,
    "required": ["analyses", "overall_gaps", "evidence_ids"],
    "properties": {
        "analyses": array_of(
            REGULATORY_INTELLIGENCE_ITEM_SCHEMA, min_items=0, max_items=5
        ),
        "overall_gaps": OPEN_TEXT_LIST,
        "evidence_ids": EVIDENCE_IDS,
    },
}
