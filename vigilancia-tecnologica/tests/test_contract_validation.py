"""Pruebas de validacion JSON Schema para contratos de extraccion."""

import copy

import pytest

from app.contracts.validation import (
    ContractValidationError,
    validate_document_extraction,
    validate_institutional_plan_extraction,
    validate_policy_matrix_extraction,
    validate_regulatory_intelligence,
    validate_strategic_assessment,
    validate_thematic_landscape,
)


def evidence() -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": "Texto fuente breve.",
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": "Seccion",
        "confidence": "Alta",
    }


def document_payload() -> dict:
    return {
        "document_analysis": {
            "temporary_id": "analysis-1",
            "document_type": "reporte",
            "title": "Documento de prueba",
            "summary": "Resumen.",
            "preliminary_topics": ["6 GHz"],
            "technologies": ["Wi-Fi"],
            "frequency_bands": ["6 GHz"],
            "countries_regions": ["Colombia"],
            "organizations": ["ANE"],
            "actors": ["regulador"],
            "keywords": ["espectro"],
            "confidence": "Alta",
            "extraction_basis": "explicit",
            "evidence_ids": ["ev-1"],
        },
        "findings": [
            {
                "temporary_id": "finding-1",
                "finding_type": "decision_regulatoria",
                "title": "Decision",
                "description": "Descripcion.",
                "preliminary_topics": ["uso de espectro"],
                "technologies": [],
                "frequency_bands": ["6 GHz"],
                "countries_regions": [],
                "organizations": ["ANE"],
                "confidence": "Media",
                "extraction_basis": "mixed",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [
            {
                "temporary_id": "project-1",
                "project_name": "Proyecto PMGE",
                "description": "Descripcion.",
                "objectives": ["Objetivo"],
                "activities": ["Actividad"],
                "expected_outputs": ["Producto"],
                "period": "2026",
                "responsible_area": None,
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "objectives": [
            {
                "temporary_id": "objective-1",
                "objective_text": "Objetivo",
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "activities": [],
        "regulatory_agenda_initiatives": [
            {
                "temporary_id": "initiative-1",
                "initiative_name": "Iniciativa",
                "regulatory_objective": "Objetivo regulatorio",
                "deliverables": ["Entregable"],
                "period": "2027",
                "responsible_area": None,
                "confidence": "Media",
                "extraction_basis": "mixed",
                "evidence_ids": ["ev-1"],
            }
        ],
        "regulatory_agenda_deliverables": [
            {
                "temporary_id": "deliverable-1",
                "initiative_temporary_id": "initiative-1",
                "deliverable_name": "Entregable",
                "description": None,
                "period": "2027",
                "confidence": "Media",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def policy_payload() -> dict:
    return {
        "policies": [
            {
                "temporary_id": "policy-1",
                "policy_name": "Politica",
                "instrument_name": "Instrumento",
                "policy_axis": "Eje",
                "description": "Descripcion",
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "activities": [
            {
                "temporary_id": "activity-1",
                "policy_temporary_id": "policy-1",
                "activity_name": "Actividad",
                "activity_description": "Descripcion",
                "responsible_area": "Area",
                "execution_period": "2026",
                "commitments": ["Compromiso"],
                "keywords": ["politica"],
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "commitments": [
            {
                "temporary_id": "commitment-1",
                "policy_activity_temporary_id": "activity-1",
                "commitment_text": "Compromiso",
                "responsible_area": "Area",
                "period": "2026",
                "confidence": "Media",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def thematic_payload() -> dict:
    return {
        "corpus_summary": "Resumen transversal.",
        "themes": [
            {
                "temporary_id": "theme-1",
                "name": "Conectividad rural",
                "definition": "Tema abierto.",
                "scope": "Corpus de vigilancia.",
                "subthemes": [],
                "technologies": ["5G"],
                "frequency_bands": [],
                "countries_regions": ["Colombia"],
                "organizations": [],
                "finding_ids": ["finding-id"],
                "evidence_ids": ["ev-1"],
                "change_action": "create",
                "previous_topic_ids": [],
                "confidence": "Alta",
                "extraction_basis": "mixed",
            }
        ],
        "trends": [
            {
                "temporary_id": "trend-1",
                "name": "Mayor interes",
                "description": "Descripcion.",
                "related_theme_temporary_ids": ["theme-1"],
                "direction": "growing",
                "time_horizon": "medium_term",
                "first_observed_date": None,
                "latest_observed_date": None,
                "countries_regions": [],
                "organizations": [],
                "finding_ids": ["finding-id"],
                "evidence_ids": ["ev-1"],
                "confidence": "Media",
            }
        ],
        "emerging_signals": [
            {
                "temporary_id": "signal-1",
                "title": "Senal",
                "description": "Descripcion.",
                "novelty_explanation": "Novedad.",
                "related_theme_temporary_ids": ["theme-1"],
                "finding_ids": ["finding-id"],
                "evidence_ids": ["ev-1"],
                "confidence": "Baja",
            }
        ],
        "evidence_ids": ["ev-1"],
    }


def regulatory_payload() -> dict:
    return {
        "analyses": [
            {
                "temporary_id": "reg-1",
                "theme_id": "theme-uuid",
                "international_situation": "Situacion.",
                "regulatory_debate": "Debate.",
                "countries_regions": ["Brasil"],
                "organizations": ["Regulador"],
                "agenda_item_ids": ["agenda-uuid"],
                "relationship_type": "partially_covered",
                "coverage_explanation": "Cobertura parcial.",
                "implications_for_ane": "Implicaciones.",
                "finding_ids": ["finding-id"],
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
                "extraction_basis": "mixed",
            }
        ],
        "overall_gaps": [],
        "evidence_ids": ["ev-1"],
    }


def strategic_payload() -> dict:
    return {
        "importance_assessments": [
            {
                "temporary_id": "importance-1",
                "subject_type": "theme",
                "subject_id": "theme-uuid",
                "dimensions": {
                    "ane_relevance": 5,
                    "magnitude": 4,
                    "urgency": 3,
                    "evidence_strength": 4,
                    "institutional_scope": 5,
                },
                "level": "Alta",
                "rationale": "Justificacion.",
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
            }
        ],
        "opportunity_assessments": [
            {
                "temporary_id": "opportunity-1",
                "theme_id": "theme-uuid",
                "policy_activity_ids": ["activity-uuid"],
                "dimensions": {
                    "policy_gap": 4,
                    "institutional_relevance": 5,
                    "actionability": 3,
                    "evidence_maturity": 4,
                    "timing": 3,
                },
                "level": "Media",
                "rationale": "Justificacion.",
                "suggested_action": "Accion sugerida.",
                "evidence_ids": ["ev-1"],
                "confidence": "Media",
            }
        ],
        "alignment_assessments": [
            {
                "temporary_id": "alignment-1",
                "theme_id": "theme-uuid",
                "pmge_project_ids": ["project-uuid"],
                "dimensions": {
                    "objective_match": 4,
                    "activity_match": 3,
                    "deliverable_match": 3,
                    "temporal_match": 2,
                    "evidence_strength": 4,
                },
                "level": "Media",
                "rationale": "Justificacion.",
                "alignment_type": "partial",
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
            }
        ],
    }


def assert_invalid(payload: dict, validator, expected: str) -> str:
    with pytest.raises(ContractValidationError) as exc_info:
        validator(payload)
    message = str(exc_info.value)
    assert expected in message
    return message


def test_minimal_valid_payloads_for_each_contract() -> None:
    assert validate_document_extraction(document_payload()) == document_payload()
    assert validate_institutional_plan_extraction(institutional_payload()) == institutional_payload()
    assert validate_policy_matrix_extraction(policy_payload()) == policy_payload()
    assert validate_thematic_landscape(thematic_payload()) == thematic_payload()
    assert validate_regulatory_intelligence(regulatory_payload()) == regulatory_payload()
    assert validate_strategic_assessment(strategic_payload()) == strategic_payload()


def test_missing_required_field_is_rejected_with_readable_path() -> None:
    payload = document_payload()
    del payload["document_analysis"]["title"]

    message = assert_invalid(payload, validate_document_extraction, "DocumentExtraction.document_analysis")
    assert "campo obligatorio ausente: 'title'" in message
    assert "rule=required" in message


def test_invalid_confidence_is_rejected_with_nested_path() -> None:
    payload = document_payload()
    payload["findings"][0]["confidence"] = "Muy alta"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.findings[0].confidence",
    )
    assert "'Muy alta' is not one of ['Alta', 'Media', 'Baja']" in message
    assert "rule=enum" in message


def test_invalid_extraction_basis_is_rejected() -> None:
    payload = policy_payload()
    payload["activities"][0]["extraction_basis"] = "contextual"

    message = assert_invalid(
        payload,
        validate_policy_matrix_extraction,
        "PolicyMatrixExtraction.activities[0].extraction_basis",
    )
    assert "contextual" in message
    assert "rule=enum" in message


def test_quote_longer_than_500_characters_is_rejected() -> None:
    payload = institutional_payload()
    payload["evidence"][0]["quote"] = "x" * 501

    message = assert_invalid(
        payload,
        validate_institutional_plan_extraction,
        "InstitutionalPlanExtraction.evidence[0].quote",
    )
    assert "too long" in message
    assert "rule=maxLength" in message


def test_additional_property_is_rejected() -> None:
    payload = document_payload()
    payload["document_analysis"]["unexpected"] = "no permitido"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.document_analysis",
    )
    assert "propiedad adicional no permitida" in message
    assert "unexpected" in message
    assert "rule=additionalProperties" in message


def test_wrong_evidence_ids_type_is_rejected() -> None:
    payload = copy.deepcopy(policy_payload())
    payload["activities"][0]["evidence_ids"] = "ev-1"

    message = assert_invalid(
        payload,
        validate_policy_matrix_extraction,
        "PolicyMatrixExtraction.activities[0].evidence_ids",
    )
    assert "is not of type 'array'" in message
    assert "rule=type" in message


def test_wrong_nested_field_type_is_rejected() -> None:
    payload = document_payload()
    payload["findings"][0]["technologies"] = "5G"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.findings[0].technologies",
    )
    assert "is not of type 'array'" in message


def test_invalid_thematic_change_action_is_rejected() -> None:
    payload = thematic_payload()
    payload["themes"][0]["change_action"] = "combine"

    message = assert_invalid(
        payload,
        validate_thematic_landscape,
        "ThematicLandscape.themes[0].change_action",
    )
    assert "combine" in message
    assert "rule=enum" in message


def test_invalid_trend_direction_is_rejected() -> None:
    payload = thematic_payload()
    payload["trends"][0]["direction"] = "accelerating"

    message = assert_invalid(
        payload,
        validate_thematic_landscape,
        "ThematicLandscape.trends[0].direction",
    )
    assert "accelerating" in message
    assert "rule=enum" in message


def test_invalid_relationship_type_is_rejected() -> None:
    payload = regulatory_payload()
    payload["analyses"][0]["relationship_type"] = "unknown"

    message = assert_invalid(
        payload,
        validate_regulatory_intelligence,
        "RegulatoryIntelligence.analyses[0].relationship_type",
    )
    assert "unknown" in message
    assert "rule=enum" in message


def test_regulatory_analysis_without_theme_reference_is_allowed() -> None:
    payload = regulatory_payload()
    del payload["analyses"][0]["theme_id"]

    assert validate_regulatory_intelligence(payload) == payload


def test_strategic_dimension_above_five_is_rejected_with_readable_path() -> None:
    payload = strategic_payload()
    payload["importance_assessments"][0]["dimensions"]["urgency"] = 6

    message = assert_invalid(
        payload,
        validate_strategic_assessment,
        "StrategicAssessment.importance_assessments[0].dimensions.urgency",
    )
    assert "greater than the maximum of 5" in message
    assert "rule=maximum" in message


def test_strategic_total_score_is_rejected() -> None:
    payload = strategic_payload()
    payload["importance_assessments"][0]["score"] = 90

    message = assert_invalid(
        payload,
        validate_strategic_assessment,
        "StrategicAssessment.importance_assessments[0]",
    )
    assert "propiedad adicional no permitida" in message
    assert "score" in message


def test_transversal_additional_property_is_rejected() -> None:
    payload = regulatory_payload()
    payload["analyses"][0]["invented"] = True

    message = assert_invalid(
        payload,
        validate_regulatory_intelligence,
        "RegulatoryIntelligence.analyses[0]",
    )
    assert "invented" in message
    assert "rule=additionalProperties" in message
