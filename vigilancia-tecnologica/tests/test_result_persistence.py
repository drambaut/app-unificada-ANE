"""Pruebas de normalizacion y persistencia abstracta de resultados."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from dataclasses import replace

import pytest

import app.results.normalizer as normalizer_module
import app.results.service as service_module
from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import Document, DocumentStatus, JobStatus, JobType, SourceType
from app.documents.service import DocumentService
from app.evidence.models import (
    EvidenceValidationItem,
    EvidenceValidationReport,
    EvidenceValidationStatus,
)
from app.llm.service import ExtractionResult
from app.results.errors import (
    DuplicateResultError,
    ResultNormalizationError,
    ResultPersistenceWorkflowError,
)
from app.results.in_memory_repository import InMemoryResultRepository
from app.results.normalizer import ResultNormalizer
from app.results.service import ResultPersistenceService


FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def uuid_factory():
    counter = {"value": 0}

    def next_uuid() -> str:
        counter["value"] += 1
        return f"uuid-{counter['value']}"

    return next_uuid


def evidence(evidence_id: str = "ev-1", quote: str = "Texto fuente") -> dict:
    return {
        "temporary_id": evidence_id,
        "quote": quote,
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": None,
        "confidence": "Alta",
    }


def document_payload() -> dict:
    return {
        "document_analysis": {
            "temporary_id": "analysis-1",
            "document_type": "reporte",
            "title": "Documento",
            "summary": "Resumen",
            "preliminary_topics": [],
            "technologies": [],
            "frequency_bands": [],
            "countries_regions": [],
            "organizations": [],
            "actors": [],
            "keywords": [],
            "confidence": "Alta",
            "extraction_basis": "explicit",
            "evidence_ids": ["ev-1"],
        },
        "findings": [
            {
                "temporary_id": "finding-1",
                "finding_type": "riesgo",
                "title": "Riesgo",
                "description": "Descripcion",
                "preliminary_topics": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
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
                "description": "Desc",
                "objectives": ["Objetivo"],
                "activities": ["Actividad"],
                "expected_outputs": [],
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
        "activities": [
            {
                "temporary_id": "activity-1",
                "activity_name": "Actividad",
                "activity_description": "Desc",
                "responsible_area": None,
                "period": "2026",
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "regulatory_agenda_initiatives": [
            {
                "temporary_id": "initiative-1",
                "initiative_name": "Agenda",
                "regulatory_objective": "Objetivo",
                "deliverables": [],
                "period": "2027",
                "responsible_area": None,
                "confidence": "Alta",
                "extraction_basis": "explicit",
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
                "confidence": "Alta",
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
                "instrument_name": None,
                "policy_axis": None,
                "description": None,
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "activities": [
            {
                "temporary_id": "policy-activity-1",
                "policy_temporary_id": "policy-1",
                "activity_name": "Actividad",
                "activity_description": "Desc",
                "responsible_area": None,
                "execution_period": "2026",
                "commitments": [],
                "keywords": [],
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "commitments": [
            {
                "temporary_id": "commitment-1",
                "policy_activity_temporary_id": "policy-activity-1",
                "commitment_text": "Compromiso",
                "responsible_area": None,
                "period": "2026",
                "confidence": "Media",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def extraction(payload: dict, contract_name: str = "DocumentExtraction") -> ExtractionResult:
    prompt_id = {
        "DocumentExtraction": "document_extraction",
        "InstitutionalPlanExtraction": "institutional_plan_extraction",
        "PolicyMatrixExtraction": "policy_matrix_extraction",
    }[contract_name]
    return ExtractionResult(
        payload=payload,
        prompt_id=prompt_id,
        prompt_version="v1",
        contract_name=contract_name,
        model_name="fake-model",
    )


def report(document_id: str = "doc-1", valid: bool = True) -> EvidenceValidationReport:
    item = EvidenceValidationItem(
        evidence_id="ev-1",
        status=EvidenceValidationStatus.VERIFIED if valid else EvidenceValidationStatus.NOT_FOUND,
        matched_chunk_id="chunk-1" if valid else None,
        message="ok" if valid else "no",
        page_number=1,
        sheet_name=None,
        row_reference=None,
    )
    return EvidenceValidationReport(
        document_id=document_id,
        items=[item],
        total=1,
        verified_count=1 if valid else 0,
        invalid_count=0 if valid else 1,
        is_valid=valid,
    )


def make_document(document_id: str = "doc-1") -> Document:
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository)
    registration = service.register_document(
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"doc",
    )
    return replace_document_id(registration.document, document_id)


def replace_document_id(document: Document, document_id: str) -> Document:
    from dataclasses import replace

    return replace(document, id=document_id)


def normalizer() -> ResultNormalizer:
    return ResultNormalizer(uuid_factory=uuid_factory(), clock=lambda: FIXED_NOW)


def test_uuid_replaces_temporary_id_and_evidence_relations() -> None:
    bundle = normalizer().normalize(
        make_document(), extraction(document_payload()), report()
    )

    assert bundle.document_analysis.id == "uuid-1"
    assert bundle.findings[0].id == "uuid-2"
    assert bundle.evidence[0].id == "uuid-3"
    assert "temporary_id" not in bundle.findings[0].data
    assert bundle.findings[0].data["evidence_ids"] == ["uuid-3"]
    assert bundle.evidence[0].data["matched_chunk_id"] == "chunk-1"
    assert bundle.evidence[0].data["page_number"] == 1


def test_pmge_and_agenda_relations_are_preserved_with_final_ids() -> None:
    bundle = normalizer().normalize(
        make_document(),
        extraction(institutional_payload(), "InstitutionalPlanExtraction"),
        report(),
    )

    assert bundle.pmge_projects[0].data["evidence_ids"] == ["uuid-6"]
    assert bundle.pmge_objectives[0].data["evidence_ids"] == ["uuid-6"]
    assert bundle.pmge_activities[0].data["evidence_ids"] == ["uuid-6"]
    assert bundle.regulatory_deliverables[0].data["initiative_id"] == bundle.regulatory_agenda_initiatives[0].id


def test_policy_matrix_relations_are_preserved_with_final_ids() -> None:
    bundle = normalizer().normalize(
        make_document(),
        extraction(policy_payload(), "PolicyMatrixExtraction"),
        report(),
    )

    assert bundle.policy_activities[0].data["policy_id"] == bundle.policies[0].id
    assert bundle.policy_commitments[0].data["policy_activity_id"] == bundle.policy_activities[0].id
    assert bundle.policy_activities[0].data["evidence_ids"] == [bundle.evidence[0].id]


def test_canonical_key_is_deterministic() -> None:
    first = normalizer().normalize(make_document(), extraction(document_payload()), report())
    second = normalizer().normalize(make_document(), extraction(document_payload()), report())

    assert first.findings[0].canonical_key == second.findings[0].canonical_key
    assert first.evidence[0].canonical_key == second.evidence[0].canonical_key
    assert first.findings[0].canonical_key == "finding|doc-1|riesgo|riesgo"


def test_canonical_key_entity_type_prevents_name_collisions() -> None:
    payload = policy_payload()
    payload["policies"][0]["policy_name"] = "Mismo Nombre"
    payload["activities"][0]["activity_name"] = "Mismo Nombre"

    bundle = normalizer().normalize(
        make_document(),
        extraction(payload, "PolicyMatrixExtraction"),
        report(),
    )

    assert bundle.policies[0].canonical_key.startswith("policy|")
    assert bundle.policy_activities[0].canonical_key.startswith("policy_activity|")
    assert bundle.policies[0].canonical_key != bundle.policy_activities[0].canonical_key


def test_duplicate_canonical_keys_are_disambiguated_deterministically() -> None:
    payload = document_payload()
    duplicate = copy.deepcopy(payload["findings"][0])
    duplicate["temporary_id"] = "finding-2"
    payload["findings"].append(duplicate)

    bundle = normalizer().normalize(make_document(), extraction(payload), report())

    assert bundle.findings[0].canonical_key == "finding|doc-1|riesgo|riesgo"
    assert bundle.findings[1].canonical_key == "finding|doc-1|riesgo|riesgo|duplicate-2"


def test_dependent_canonical_keys_use_final_uuid() -> None:
    institutional = normalizer().normalize(
        make_document(),
        extraction(institutional_payload(), "InstitutionalPlanExtraction"),
        report(),
    )
    policy = normalizer().normalize(
        make_document(),
        extraction(policy_payload(), "PolicyMatrixExtraction"),
        report(),
    )

    assert institutional.regulatory_deliverables[0].canonical_key == (
        f"agenda_deliverable|doc-1|{institutional.regulatory_agenda_initiatives[0].id}|entregable"
    )
    assert policy.policy_activities[0].canonical_key == (
        f"policy_activity|doc-1|{policy.policies[0].id}|actividad"
    )
    assert policy.policy_commitments[0].canonical_key == (
        f"policy_commitment|doc-1|{policy.policy_activities[0].id}|compromiso"
    )


def test_no_canonical_key_contains_temporary_id() -> None:
    bundle = normalizer().normalize(
        make_document(),
        extraction(policy_payload(), "PolicyMatrixExtraction"),
        report(),
    )

    for record in bundle.all_records():
        assert "temporary" not in record.canonical_key
        assert "policy-1" not in record.canonical_key
        assert "policy-activity-1" not in record.canonical_key
        assert "ev-1" not in record.canonical_key


def test_payload_original_is_not_modified() -> None:
    payload = document_payload()
    original = copy.deepcopy(payload)

    normalizer().normalize(make_document(), extraction(payload), report())

    assert payload == original


def test_invalid_evidence_report_is_rejected() -> None:
    with pytest.raises(ResultNormalizationError):
        normalizer().normalize(make_document(), extraction(document_payload()), report(valid=False))


def test_unvalidated_evidence_entry_is_rejected_with_clear_error() -> None:
    payload = document_payload()
    payload["evidence"].append(evidence("E1_cover", "Portada"))

    with pytest.raises(ResultNormalizationError, match="E1_cover"):
        normalizer().normalize(make_document(), extraction(payload), report())


def test_missing_temporary_reference_is_rejected() -> None:
    payload = document_payload()
    payload["findings"][0]["evidence_ids"] = ["ev-missing"]

    with pytest.raises(ResultNormalizationError, match="ev-missing"):
        normalizer().normalize(make_document(), extraction(payload), report())


def test_duplicate_temporary_id_is_rejected() -> None:
    payload = document_payload()
    payload["findings"][0]["temporary_id"] = "analysis-1"

    with pytest.raises(ResultNormalizationError, match="duplicado"):
        normalizer().normalize(make_document(), extraction(payload), report())


def test_in_memory_repository_is_atomic_on_duplicate_key() -> None:
    repository = InMemoryResultRepository()
    payload = document_payload()
    duplicate = copy.deepcopy(payload["findings"][0])
    duplicate["temporary_id"] = "finding-2"
    payload["findings"].append(duplicate)
    bundle = normalizer().normalize(make_document(), extraction(payload), report())
    bundle.findings[1] = replace(
        bundle.findings[1],
        canonical_key=bundle.findings[0].canonical_key,
    )

    with pytest.raises(DuplicateResultError):
        repository.save_bundle(bundle)

    assert repository.get_bundle("doc-1") is None


def test_in_memory_repository_rejects_repeated_document() -> None:
    repository = InMemoryResultRepository()
    bundle = normalizer().normalize(make_document(), extraction(document_payload()), report())
    repository.save_bundle(bundle)

    with pytest.raises(DuplicateResultError):
        repository.save_bundle(bundle)


def setup_ready_to_persist():
    document_repository = InMemoryDocumentRepository()
    document_service = DocumentService(document_repository)
    registration = document_service.register_document(
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"doc",
    )
    document_id = registration.document.id
    prep_job = registration.job
    document_repository.update_job_status(prep_job.id, JobStatus.COMPLETED)
    document_service.transition_document_status(document_id, DocumentStatus.PREPARING)
    document_service.transition_document_status(document_id, DocumentStatus.PREPARED)
    analysis_job = document_service.create_analysis_job(document_id)
    document_service.transition_document_status(document_id, DocumentStatus.ANALYZING)
    document_repository.update_job_status(analysis_job.id, JobStatus.COMPLETED)
    document_service.transition_document_status(document_id, DocumentStatus.VALIDATING)
    validation_job = document_service.create_evidence_validation_job(document_id)
    document_repository.update_job_status(validation_job.id, JobStatus.COMPLETED)
    document_service.transition_document_status(document_id, DocumentStatus.READY_TO_PERSIST)
    persistence_job = document_service.create_result_persistence_job(document_id)
    return document_repository, document_id, persistence_job


def test_persistence_flow_success_finishes_processed() -> None:
    document_repository, document_id, persistence_job = setup_ready_to_persist()
    result_repository = InMemoryResultRepository()
    service = ResultPersistenceService(
        document_repository=document_repository,
        result_repository=result_repository,
        normalizer=normalizer(),
    )

    result = service.persist(
        document_id=document_id,
        extraction_result=extraction(document_payload()),
        evidence_report=report(document_id),
    )

    assert result.document.status == DocumentStatus.PROCESSED
    assert result.result_persistence_job.status == JobStatus.COMPLETED
    assert result_repository.get_bundle(document_id) == result.bundle
    assert document_repository.get_job(persistence_job.id).status == JobStatus.COMPLETED


def test_persistence_flow_failure_marks_failed_without_partial_save() -> None:
    document_repository, document_id, persistence_job = setup_ready_to_persist()
    result_repository = InMemoryResultRepository()
    service = ResultPersistenceService(
        document_repository=document_repository,
        result_repository=result_repository,
        normalizer=normalizer(),
    )

    with pytest.raises(ResultPersistenceWorkflowError):
        service.persist(
            document_id=document_id,
            extraction_result=extraction(document_payload()),
            evidence_report=report(document_id, valid=False),
        )

    assert result_repository.get_bundle(document_id) is None
    assert document_repository.get_document(document_id).status == DocumentStatus.FAILED
    assert document_repository.get_job(persistence_job.id).status == JobStatus.FAILED


def test_document_in_wrong_state_is_rejected() -> None:
    document_repository = InMemoryDocumentRepository()
    document_service = DocumentService(document_repository)
    registration = document_service.register_document(
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"doc",
    )
    service = ResultPersistenceService(
        document_repository=document_repository,
        result_repository=InMemoryResultRepository(),
        normalizer=normalizer(),
    )

    with pytest.raises(ResultPersistenceWorkflowError, match="ready_to_persist"):
        service.persist(
            document_id=registration.document.id,
            extraction_result=extraction(document_payload()),
            evidence_report=report(registration.document.id),
        )


def test_missing_or_wrong_job_is_rejected() -> None:
    document_repository, document_id, persistence_job = setup_ready_to_persist()
    document_repository.update_job_status(persistence_job.id, JobStatus.RUNNING)
    service = ResultPersistenceService(
        document_repository=document_repository,
        result_repository=InMemoryResultRepository(),
        normalizer=normalizer(),
    )

    with pytest.raises(ResultPersistenceWorkflowError, match="RESULT_PERSISTENCE"):
        service.persist(
            document_id=document_id,
            extraction_result=extraction(document_payload()),
            evidence_report=report(document_id),
        )


def test_results_modules_do_not_import_gemini_or_supabase() -> None:
    normalizer_source = normalizer_module.__loader__.get_source(normalizer_module.__name__)
    service_source = service_module.__loader__.get_source(service_module.__name__)

    assert "google.genai" not in normalizer_source
    assert "google.genai" not in service_source
    assert "supabase" not in normalizer_source.lower()
    assert "supabase" not in service_source.lower()
