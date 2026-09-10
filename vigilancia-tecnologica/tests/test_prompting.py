"""Pruebas para prompts especializados y versionados."""

from pathlib import Path

import pytest

import app.llm_extract as llm_module
from app.core.settings import PROJECT_ROOT
from app.prompting import PROMPT_REGISTRY, load_prompt
from app.prompting.registry import get_prompt_spec


V1_PROMPTS = {
    "document_extraction": "DocumentExtraction",
    "institutional_plan_extraction": "InstitutionalPlanExtraction",
    "policy_matrix_extraction": "PolicyMatrixExtraction",
    "thematic_landscape": "ThematicLandscape",
    "regulatory_intelligence": "RegulatoryIntelligence",
    "strategic_assessment": "StrategicAssessment",
}


def test_v1_prompt_files_exist() -> None:
    for prompt_id in V1_PROMPTS:
        spec = get_prompt_spec(prompt_id, "v1")
        assert (PROJECT_ROOT / spec.path).is_file()


def test_load_prompt_by_id_and_version() -> None:
    spec, content = load_prompt("document_extraction", "v1")

    assert spec.prompt_id == "document_extraction"
    assert spec.version == "v1"
    assert spec.status == "active"
    assert "Devuelve unicamente JSON valido" in content


def test_missing_prompt_fails_clearly() -> None:
    with pytest.raises(KeyError, match="No existe prompt registrado"):
        load_prompt("missing_prompt", "v1")


def test_registered_contracts_are_correct() -> None:
    contracts = {
        spec.prompt_id: spec.contract
        for spec in PROMPT_REGISTRY
        if spec.version == "v1"
    }

    assert contracts == V1_PROMPTS


def test_document_prompt_avoids_closed_strategic_taxonomy_references() -> None:
    _, content = load_prompt("document_extraction", "v1")

    assert "TEMAS_ESTRATEGICOS" not in content
    assert "LINEAS_PMGE" not in content
    assert "No asignes lineas PMGE" in content
    assert "No generes recomendaciones" in content


def test_prompts_include_required_json_evidence_and_confidence_instructions() -> None:
    for prompt_id in V1_PROMPTS:
        _, content = load_prompt(prompt_id, "v1")
        assert "JSON Schema" in content or "Schema" in content
        assert "response_schema" in content
        assert "Devuelve unicamente JSON valido" in content
        assert "temporary_id" in content
        assert "confidence unicamente con estos valores: Alta, Media o Baja" in content
        assert "evidence" in content or "evidencia" in content

    for prompt_id in (
        "document_extraction",
        "institutional_plan_extraction",
        "policy_matrix_extraction",
    ):
        _, content = load_prompt(prompt_id, "v1")
        assert "extraction_basis unicamente con estos valores: explicit, inferred o mixed" in content
        assert "quote" in content
        assert "maximo 500 caracteres" in content


def test_transversal_prompts_are_active_and_avoid_closed_taxonomies() -> None:
    for prompt_id in (
        "thematic_landscape",
        "regulatory_intelligence",
        "strategic_assessment",
    ):
        spec, content = load_prompt(prompt_id, "v1")
        assert spec.status == "active"
        assert "TEMAS_ESTRATEGICOS" not in content
        assert "taxonomias cerradas" in content
        assert "Devuelve unicamente JSON valido" in content
        assert "response_schema" in content
        assert "evidence_ids" in content
        assert "No crees citas textuales nuevas" in content


def test_thematic_landscape_prompt_mentions_thematic_changes() -> None:
    _, content = load_prompt("thematic_landscape", "v1")

    assert "change_action" in content
    assert "create, retain, rename, merge, split, retire" in content
    assert "fusiones" in content
    assert "divisiones" in content
    assert "tendencia" in content
    assert "senales emergentes" in content


def test_regulatory_intelligence_prompt_requires_agenda() -> None:
    _, content = load_prompt("regulatory_intelligence", "v1")

    assert "Agenda Regulatoria" in content
    assert "agenda_item_ids" in content
    assert "No inventes iniciativas" in content
    assert "covered, partially_covered, gap, complementary, tension, no_direct_relation" in content


def test_strategic_assessment_prompt_separates_three_assessments_without_scores() -> None:
    _, content = load_prompt("strategic_assessment", "v1")

    assert "importance_assessments" in content
    assert "opportunity_assessments" in content
    assert "alignment_assessments" in content
    assert "No produzcas score total" in content
    assert "No apliques pesos" in content
    assert "policy_activity_ids" in content
    assert "pmge_project_ids" in content


def test_institutional_plan_prompt_separates_pmge_and_agenda() -> None:
    _, content = load_prompt("institutional_plan_extraction", "v1")

    assert "PMGE" in content
    assert "Agenda Regulatoria" in content
    assert "Extrae por separado" in content
    assert "No cruces todavia" in content


def test_policy_matrix_prompt_preserves_excel_references() -> None:
    _, content = load_prompt("policy_matrix_extraction", "v1")

    assert "sheet_name" in content
    assert "row_reference" in content
    assert "No hagas alineacion" in content


def test_legacy_prompt_compatibility_is_preserved() -> None:
    legacy_path = PROJECT_ROOT / "prompts" / "legacy" / "extraction_prompt.txt"
    current_path = PROJECT_ROOT / "prompts" / "extraction_prompt.txt"

    assert legacy_path.is_file()
    assert current_path.is_file()
    assert llm_module.PROMPT_PATH == current_path
    assert legacy_path.read_text(encoding="utf-8") == current_path.read_text(
        encoding="utf-8"
    )
    legacy_spec, legacy_content = load_prompt("legacy_document_extraction", "legacy")
    assert legacy_spec.status == "legacy"
    assert legacy_content


def test_loader_does_not_modify_prompt_files() -> None:
    spec = get_prompt_spec("document_extraction", "v1")
    prompt_path = PROJECT_ROOT / spec.path
    before = Path(prompt_path).stat().st_mtime_ns

    load_prompt("document_extraction", "v1")

    after = Path(prompt_path).stat().st_mtime_ns
    assert after == before
