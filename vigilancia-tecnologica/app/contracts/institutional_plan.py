"""Contratos para extraccion de PMGE y Agenda Regulatoria."""

from app.contracts.common import (
    CONFIDENCE,
    EVIDENCE_IDS,
    EVIDENCE_SCHEMA,
    EXTRACTION_BASIS,
    OPEN_TEXT_LIST,
    TEMPORARY_ID,
    array_of,
)

PMGE_PROJECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "project_name",
        "description",
        "objectives",
        "activities",
        "expected_outputs",
        "period",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "project_name": {"type": "string"},
        "description": {"type": "string"},
        "objectives": OPEN_TEXT_LIST,
        "activities": OPEN_TEXT_LIST,
        "expected_outputs": OPEN_TEXT_LIST,
        "period": {"type": ["string", "null"]},
        "responsible_area": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

PLAN_OBJECTIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["temporary_id", "objective_text", "confidence", "extraction_basis", "evidence_ids"],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "objective_text": {"type": "string"},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

PLAN_ACTIVITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "activity_name",
        "activity_description",
        "responsible_area",
        "period",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "activity_name": {"type": "string"},
        "activity_description": {"type": "string"},
        "responsible_area": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

AGENDA_INITIATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "initiative_name",
        "regulatory_objective",
        "deliverables",
        "period",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "initiative_name": {"type": "string"},
        "regulatory_objective": {"type": "string"},
        "deliverables": OPEN_TEXT_LIST,
        "period": {"type": ["string", "null"]},
        "responsible_area": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

AGENDA_DELIVERABLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "initiative_temporary_id",
        "deliverable_name",
        "description",
        "period",
        "confidence",
        "extraction_basis",
        "evidence_ids",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "initiative_temporary_id": {"type": "string"},
        "deliverable_name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
        "evidence_ids": EVIDENCE_IDS,
    },
}

INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "InstitutionalPlanExtraction",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "pmge_projects",
        "objectives",
        "activities",
        "regulatory_agenda_initiatives",
        "regulatory_agenda_deliverables",
        "evidence",
    ],
    "properties": {
        "pmge_projects": array_of(PMGE_PROJECT_SCHEMA, min_items=0),
        "objectives": array_of(PLAN_OBJECTIVE_SCHEMA, min_items=0),
        "activities": array_of(PLAN_ACTIVITY_SCHEMA, min_items=0),
        "regulatory_agenda_initiatives": array_of(AGENDA_INITIATIVE_SCHEMA, min_items=0),
        "regulatory_agenda_deliverables": array_of(AGENDA_DELIVERABLE_SCHEMA, min_items=0),
        "evidence": array_of(EVIDENCE_SCHEMA, min_items=0),
    },
}
