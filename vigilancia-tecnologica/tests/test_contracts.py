"""Pruebas de contratos JSON Schema para extracciones futuras."""

import json

from app.contracts import (
    DOCUMENT_EXTRACTION_SCHEMA,
    INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
    POLICY_MATRIX_EXTRACTION_SCHEMA,
    REGULATORY_INTELLIGENCE_SCHEMA,
    STRATEGIC_ASSESSMENT_SCHEMA,
    THEMATIC_LANDSCAPE_SCHEMA,
)
from app.contracts.common import (
    CONFIDENCE_VALUES,
    EVIDENCE_SCHEMA,
    EXTRACTION_BASIS_VALUES,
)
from app.contracts.document_extraction import FINDING_TYPE_VALUES
from app.contracts.regulatory_intelligence import RELATIONSHIP_TYPE_VALUES
from app.contracts.strategic_assessment import ALIGNMENT_TYPE_VALUES
from app.contracts.thematic_landscape import (
    CHANGE_ACTION_VALUES,
    TREND_DIRECTION_VALUES,
)


def _properties(schema: dict) -> dict:
    return schema["properties"]


def test_contracts_are_json_serializable() -> None:
    for schema in (
        DOCUMENT_EXTRACTION_SCHEMA,
        INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
        POLICY_MATRIX_EXTRACTION_SCHEMA,
        THEMATIC_LANDSCAPE_SCHEMA,
        REGULATORY_INTELLIGENCE_SCHEMA,
        STRATEGIC_ASSESSMENT_SCHEMA,
    ):
        encoded = json.dumps(schema, ensure_ascii=False)
        assert encoded.startswith("{")


def test_common_evidence_contract_supports_pdf_and_excel_locations() -> None:
    properties = _properties(EVIDENCE_SCHEMA)

    assert "quote" in EVIDENCE_SCHEMA["required"]
    assert properties["quote"]["maxLength"] == 500
    assert properties["page_number"]["type"] == ["integer", "null"]
    assert properties["sheet_name"]["type"] == ["string", "null"]
    assert properties["row_reference"]["type"] == ["string", "null"]
    assert properties["confidence"]["enum"] == CONFIDENCE_VALUES
    assert "inferencia_contextual" not in properties["evidence_type"]["enum"]


def test_document_extraction_required_fields_and_zero_many_findings() -> None:
    assert DOCUMENT_EXTRACTION_SCHEMA["required"] == [
        "document_analysis",
        "findings",
        "evidence",
    ]
    findings = _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]
    assert findings["type"] == "array"
    assert findings["minItems"] == 0

    analysis_required = _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"][
        "required"
    ]
    assert "temporary_id" in analysis_required
    assert "preliminary_topics" in analysis_required
    assert "evidence_ids" in analysis_required


def test_document_finding_uses_only_functional_general_categories() -> None:
    expected = [
        "desarrollo_tecnologico",
        "decision_regulatoria",
        "consulta_publica",
        "propuesta_regulatoria",
        "asignacion_o_planificacion",
        "estudio_o_evidencia",
        "riesgo",
        "oportunidad",
        "posicion_institucional",
        "otro",
    ]
    assert FINDING_TYPE_VALUES == expected

    finding_schema = _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"]
    finding_properties = _properties(finding_schema)
    assert finding_properties["finding_type"]["enum"] == expected
    assert "recommended_follow_up" not in finding_properties
    assert "pmge_line" not in finding_properties
    assert "strategic_topic" not in finding_properties


def test_document_extraction_does_not_use_closed_topic_taxonomies() -> None:
    analysis_properties = _properties(
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"]
    )
    finding_properties = _properties(
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"]
    )

    for properties in (analysis_properties, finding_properties):
        assert "strategic_topic" not in properties
        assert "pmge_line" not in properties
        assert "agenda_input_type" not in properties
        assert "enum" not in properties["preliminary_topics"]["items"]


def test_confidence_and_extraction_basis_enums_are_consistent() -> None:
    schemas = [
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"],
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"],
        _properties(INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA)["pmge_projects"]["items"],
        _properties(POLICY_MATRIX_EXTRACTION_SCHEMA)["activities"]["items"],
    ]

    for schema in schemas:
        properties = _properties(schema)
        assert properties["confidence"]["enum"] == CONFIDENCE_VALUES
        assert properties["extraction_basis"]["enum"] == EXTRACTION_BASIS_VALUES


def test_institutional_plan_separates_pmge_and_regulatory_agenda() -> None:
    properties = _properties(INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA)

    assert "pmge_projects" in properties
    assert "objectives" in properties
    assert "activities" in properties
    assert "regulatory_agenda_initiatives" in properties
    assert "regulatory_agenda_deliverables" in properties
    assert properties["pmge_projects"]["type"] == "array"
    assert properties["regulatory_agenda_initiatives"]["type"] == "array"
    assert properties["pmge_projects"] != properties["regulatory_agenda_initiatives"]


def test_policy_matrix_has_policies_activities_commitments_and_evidence() -> None:
    assert POLICY_MATRIX_EXTRACTION_SCHEMA["required"] == [
        "policies",
        "activities",
        "commitments",
        "evidence",
    ]
    properties = _properties(POLICY_MATRIX_EXTRACTION_SCHEMA)

    for key in ("policies", "activities", "commitments", "evidence"):
        assert properties[key]["type"] == "array"
        assert properties[key]["minItems"] == 0

    activity_properties = _properties(properties["activities"]["items"])
    assert "temporary_id" in properties["activities"]["items"]["required"]
    assert "evidence_ids" in properties["activities"]["items"]["required"]
    assert "commitments" in activity_properties


def test_thematic_landscape_uses_open_themes_and_expected_enums() -> None:
    properties = _properties(THEMATIC_LANDSCAPE_SCHEMA)
    theme = properties["themes"]["items"]
    trend = properties["trends"]["items"]

    assert THEMATIC_LANDSCAPE_SCHEMA["required"] == [
        "corpus_summary",
        "themes",
        "trends",
        "emerging_signals",
        "evidence_ids",
    ]
    assert "enum" not in _properties(theme)["name"]
    assert properties["corpus_summary"]["maxLength"] <= 1200
    assert properties["themes"]["maxItems"] == 4
    assert properties["trends"]["maxItems"] == 4
    assert _properties(theme)["change_action"]["enum"] == CHANGE_ACTION_VALUES
    assert _properties(trend)["direction"]["enum"] == TREND_DIRECTION_VALUES
    assert "strategic_topic" not in json.dumps(THEMATIC_LANDSCAPE_SCHEMA)
    assert "TEMAS_ESTRATEGICOS" not in json.dumps(THEMATIC_LANDSCAPE_SCHEMA)


def test_regulatory_intelligence_relationship_enum_and_backend_ids() -> None:
    item = _properties(REGULATORY_INTELLIGENCE_SCHEMA)["analyses"]["items"]
    properties = _properties(item)

    assert REGULATORY_INTELLIGENCE_SCHEMA["required"] == [
        "analyses",
        "overall_gaps",
        "evidence_ids",
    ]
    assert properties["relationship_type"]["enum"] == RELATIONSHIP_TYPE_VALUES
    assert _properties(REGULATORY_INTELLIGENCE_SCHEMA)["analyses"]["maxItems"] == 5
    assert properties["agenda_item_ids"]["items"]["type"] == "string"
    assert "theme_id" in properties
    assert "theme_temporary_id" in properties


def test_strategic_assessment_separates_collections_and_has_no_total_score() -> None:
    properties = _properties(STRATEGIC_ASSESSMENT_SCHEMA)

    assert STRATEGIC_ASSESSMENT_SCHEMA["required"] == [
        "importance_assessments",
        "opportunity_assessments",
        "alignment_assessments",
    ]
    assert set(properties) == set(STRATEGIC_ASSESSMENT_SCHEMA["required"])
    assert properties["importance_assessments"]["maxItems"] == 5
    assert properties["opportunity_assessments"]["maxItems"] == 5
    assert properties["alignment_assessments"]["maxItems"] == 5
    encoded = json.dumps(STRATEGIC_ASSESSMENT_SCHEMA)
    assert "score" not in encoded
    assert "weight" not in encoded

    importance_dimensions = _properties(
        properties["importance_assessments"]["items"]
    )["dimensions"]
    for dimension in _properties(importance_dimensions).values():
        assert dimension["minimum"] == 0
        assert dimension["maximum"] == 5

    alignment = properties["alignment_assessments"]["items"]
    assert _properties(alignment)["alignment_type"]["enum"] == ALIGNMENT_TYPE_VALUES
