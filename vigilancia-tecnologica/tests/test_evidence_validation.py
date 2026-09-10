"""Pruebas de validacion de evidencia contra chunks."""

from __future__ import annotations

from dataclasses import replace

import pytest

import app.evidence.service as evidence_service_module
import app.evidence.validator as evidence_validator_module
from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    JobType,
    SourceType,
)
from app.documents.service import DocumentService
from app.evidence.errors import EvidenceValidationWorkflowError
from app.evidence.models import EvidenceValidationStatus
from app.evidence.service import EvidenceValidationWorkflow
from app.evidence.validator import EvidenceValidator


def make_document(
    *,
    file_type: str = "pdf",
    source_type: SourceType = SourceType.SURVEILLANCE,
) -> Document:
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository)
    registration = service.register_document(
        file_name=f"doc.{file_type}",
        file_type=file_type,
        source_type=source_type,
        content=b"doc",
    )
    return registration.document


def pdf_chunk(
    chunk_id: str,
    content: str,
    page_number: int,
    position: int,
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        document_id="doc-1",
        content=content,
        page_number=page_number,
        section_title=None,
        sheet_name=None,
        row_reference=None,
        content_hash=DocumentService.calculate_sha256(content.encode("utf-8")),
        position=position,
    )


def excel_chunk(
    chunk_id: str,
    content: str,
    sheet_name: str,
    row_reference: str,
    position: int,
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        document_id="doc-1",
        content=content,
        page_number=None,
        section_title=None,
        sheet_name=sheet_name,
        row_reference=row_reference,
        content_hash=DocumentService.calculate_sha256(content.encode("utf-8")),
        position=position,
    )


def evidence(
    evidence_id: str = "ev-1",
    quote: str = "texto clave",
    *,
    page_number: int | None = 1,
    sheet_name: str | None = None,
    row_reference: str | None = None,
) -> dict:
    return {
        "temporary_id": evidence_id,
        "quote": quote,
        "evidence_type": "cita_textual",
        "page_number": page_number,
        "sheet_name": sheet_name,
        "row_reference": row_reference,
        "section_title": None,
        "confidence": "Alta",
    }


def document_payload(
    evidence_items: list[dict] | None = None, evidence_ids: list[str] | None = None
) -> dict:
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
            "evidence_ids": evidence_ids or ["ev-1"],
        },
        "findings": [],
        "evidence": evidence_items or [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [
            {
                "temporary_id": "project-1",
                "project_name": "Proyecto",
                "description": "Desc",
                "objectives": [],
                "activities": [],
                "expected_outputs": [],
                "period": None,
                "responsible_area": None,
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "objectives": [],
        "activities": [],
        "regulatory_agenda_initiatives": [],
        "regulatory_agenda_deliverables": [],
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
        "activities": [],
        "commitments": [],
        "evidence": [evidence()],
    }


def status_of(report, evidence_id: str) -> EvidenceValidationStatus:
    return next(item.status for item in report.items if item.evidence_id == evidence_id)


def test_pdf_quote_on_correct_page_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk("p1", "La pagina contiene texto clave.", 1, 1),
            pdf_chunk("p2", "Otro contenido.", 2, 2),
        ],
        document_payload(),
    )

    assert report.is_valid is True
    assert report.verified_count == 1
    assert report.items[0].matched_chunk_id == "p1"


def test_pdf_quote_with_extraction_artifacts_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk(
                "p1",
                "The report describes spectrum-\nsharing and non-terrestrial "
                "networks for rural coverage.",
                1,
                1,
            )
        ],
        document_payload(
            [
                evidence(
                    quote=(
                        "spectrum sharing and non terrestrial networks "
                        "for rural coverage"
                    )
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "p1"


def test_pdf_near_literal_long_quote_is_verified_by_token_overlap() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk(
                "p1",
                "The 3.5 GHz band supports private networks, industrial "
                "automation, capacity growth, and coverage obligations.",
                1,
                1,
            )
        ],
        document_payload(
            [
                evidence(
                    quote=(
                        "The 3.5 GHz band supports private networks, "
                        "industrial automation, capacity growth, coverage "
                        "obligations."
                    )
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "p1"


def test_pdf_quote_on_wrong_page_is_relocated_when_unique() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1)],
        document_payload([evidence(page_number=2)]),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.VERIFIED
    assert report.items[0].page_number == 1
    assert report.is_valid is True


def test_pdf_quote_on_wrong_page_with_multiple_matches_is_invalid_location() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk("p1", "texto clave", 1, 1),
            pdf_chunk("p2", "texto clave", 3, 2),
        ],
        document_payload([evidence(page_number=2)]),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.INVALID_LOCATION
    assert report.is_valid is False


def test_missing_quote_is_not_found() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "otro texto", 1, 1)],
        document_payload(),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.NOT_FOUND


def test_null_page_number_with_unique_match_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1), pdf_chunk("p2", "otro", 2, 2)],
        document_payload([evidence(page_number=None)]),
    )

    assert report.is_valid is True
    assert report.items[0].page_number == 1


def test_null_page_number_with_multiple_matches_is_invalid_location() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1), pdf_chunk("p2", "texto clave", 2, 2)],
        document_payload([evidence(page_number=None)]),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.INVALID_LOCATION


def test_excel_quote_with_correct_sheet_and_row_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.POLICY_MATRIX),
        [excel_chunk("r1", "col=texto clave", "Hoja", "2", 1)],
        document_payload(
            [evidence(page_number=None, sheet_name="Hoja", row_reference="2")]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "r1"


def test_excel_quote_with_partial_overlap_on_declared_row_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.SURVEILLANCE),
        [
            excel_chunk(
                "r1",
                (
                    "row=Indicador=Fecha de elaboracion; Valor=2026-06-24; "
                    "Fuente=Cullen International; Cantidad=187"
                ),
                "Resumen",
                "4",
                1,
            )
        ],
        document_payload(
            [
                evidence(
                    quote="Elaboracion 2026-06-24 Cullen International 187",
                    page_number=None,
                    sheet_name="Resumen",
                    row_reference="4",
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "r1"


def test_excel_row_reference_label_from_llm_is_normalized() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.SURVEILLANCE),
        [excel_chunk("r1", "col=texto clave", "00_Resumen", "2", 1)],
        document_payload(
            [
                evidence(
                    page_number=None,
                    sheet_name="00_Resumen",
                    row_reference="ROW_REFERENCE: 2",
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "r1"


def test_excel_quote_with_partial_overlap_on_declared_sheet_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.SURVEILLANCE),
        [
            excel_chunk(
                "r1",
                "Tema=5G; Fuente=TeleSemana; Pais=Colombia; Ano=2026",
                "00_Resumen",
                "6",
                1,
            )
        ],
        document_payload(
            [
                evidence(
                    quote="TeleSemana Colombia 2026",
                    page_number=None,
                    sheet_name="00_Resumen",
                    row_reference="8",
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "r1"


def test_excel_quote_with_wrong_location_is_relocated_when_unique() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.POLICY_MATRIX),
        [excel_chunk("r1", "col=texto clave", "Hoja", "2", 1)],
        document_payload(
            [evidence(page_number=None, sheet_name="Otra", row_reference="9")]
        ),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.VERIFIED
    assert report.items[0].sheet_name == "Hoja"
    assert report.items[0].row_reference == "2"


def test_pdf_quote_with_partial_overlap_on_declared_page_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk(
                "p1",
                "El documento analiza tendencias de espectro, redes 5G y politicas regulatorias.",
                1,
                1,
            )
        ],
        document_payload(
            [
                evidence(
                    quote="tendencias espectro redes politicas regulatorias",
                    page_number=1,
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].matched_chunk_id == "p1"


def test_excel_quote_with_repeated_match_on_declared_sheet_is_verified() -> None:
    report = EvidenceValidator().validate(
        make_document(file_type="xlsx", source_type=SourceType.POLICY_MATRIX),
        [
            excel_chunk(
                "r1",
                "linea=Adopcion de ambientes de TI para la innovacion",
                "PLAN_ESTRATEGICO",
                "8",
                1,
            ),
            excel_chunk(
                "r2",
                "linea=Adopcion de ambientes de TI para la innovacion",
                "PLAN_ESTRATEGICO",
                "12",
                2,
            ),
            excel_chunk(
                "r3",
                "linea=Adopcion de ambientes de TI para la innovacion",
                "POA_CONSOLIDADOS METAS",
                "20",
                3,
            ),
        ],
        document_payload(
            [
                evidence(
                    quote="Adopcion de ambientes de TI para la innovacion",
                    page_number=None,
                    sheet_name="PLAN_ESTRATEGICO",
                    row_reference="10",
                )
            ]
        ),
    )

    assert report.is_valid is True
    assert report.items[0].sheet_name == "PLAN_ESTRATEGICO"


def test_missing_evidence_id_reference_is_reported() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1)],
        document_payload(evidence_ids=["ev-no-existe"]),
    )

    assert status_of(report, "ev-no-existe") == EvidenceValidationStatus.MISSING_REFERENCE
    assert report.is_valid is False


def test_unreferenced_evidence_entries_are_still_validated() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [
            pdf_chunk("p1", "texto clave", 1, 1),
            pdf_chunk("p2", "evidencia de portada", 2, 2),
        ],
        document_payload(
            [
                evidence("ev-1", quote="texto clave", page_number=1),
                evidence("E1_cover", quote="evidencia de portada", page_number=2),
            ],
            evidence_ids=["ev-1"],
        ),
    )

    assert report.is_valid is True
    assert status_of(report, "ev-1") == EvidenceValidationStatus.VERIFIED
    assert status_of(report, "E1_cover") == EvidenceValidationStatus.VERIFIED


def test_duplicate_temporary_id_is_reported() -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1)],
        document_payload([evidence(), evidence()]),
    )

    assert status_of(report, "ev-1") == EvidenceValidationStatus.DUPLICATE_ID
    assert report.is_valid is False


@pytest.mark.parametrize(
    "payload_factory",
    [document_payload, institutional_payload, policy_payload],
)
def test_nested_evidence_ids_work_for_all_contract_shapes(payload_factory) -> None:
    report = EvidenceValidator().validate(
        make_document(),
        [pdf_chunk("p1", "texto clave", 1, 1)],
        payload_factory(),
    )

    assert report.is_valid is True


def setup_validating_repository(payload_valid: bool = True):
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository)
    registration = service.register_document(
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"doc",
    )
    document_id = registration.document.id
    prep_job = registration.job
    repository.update_job_status(prep_job.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.PREPARING)
    service.transition_document_status(document_id, DocumentStatus.PREPARED)
    analysis_job = service.create_analysis_job(document_id)
    service.transition_document_status(document_id, DocumentStatus.ANALYZING)
    repository.update_job_status(analysis_job.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.VALIDATING)
    validation_job = service.create_evidence_validation_job(document_id)
    chunk = pdf_chunk("p1", "texto clave", 1, 1)
    repository.save_chunk(replace(chunk, document_id=document_id))
    payload = document_payload()
    if not payload_valid:
        payload = document_payload([evidence(quote="ausente")])
    return repository, document_id, validation_job, payload


def test_evidence_workflow_success_creates_result_persistence() -> None:
    repository, document_id, validation_job, payload = setup_validating_repository()
    workflow = EvidenceValidationWorkflow(
        repository=repository, validator=EvidenceValidator()
    )

    result = workflow.run(document_id, payload)

    assert result.report.is_valid is True
    assert result.document.status == DocumentStatus.READY_TO_PERSIST
    assert result.evidence_validation_job.status == JobStatus.COMPLETED
    assert result.result_persistence_job is not None
    assert result.result_persistence_job.job_type == JobType.RESULT_PERSISTENCE
    assert repository.get_job(validation_job.id).status == JobStatus.COMPLETED


def test_evidence_workflow_invalid_marks_document_and_job_failed() -> None:
    repository, document_id, validation_job, payload = setup_validating_repository(
        payload_valid=False
    )
    workflow = EvidenceValidationWorkflow(
        repository=repository, validator=EvidenceValidator()
    )

    result = workflow.run(document_id, payload)

    assert result.report.is_valid is False
    assert result.document.status == DocumentStatus.FAILED
    assert result.evidence_validation_job.status == JobStatus.FAILED
    assert repository.get_job(validation_job.id).error_message
    assert all(
        job.job_type != JobType.RESULT_PERSISTENCE
        for job in repository.list_jobs(document_id)
    )


def test_evidence_workflow_does_not_create_duplicate_persistence_job() -> None:
    repository, document_id, _validation_job, payload = setup_validating_repository()
    workflow = EvidenceValidationWorkflow(
        repository=repository, validator=EvidenceValidator()
    )

    workflow.run(document_id, payload)

    with pytest.raises(EvidenceValidationWorkflowError):
        workflow.run(document_id, payload)

    persistence_jobs = [
        job for job in repository.list_jobs(document_id)
        if job.job_type == JobType.RESULT_PERSISTENCE
    ]
    assert len(persistence_jobs) == 1


def test_evidence_workflow_rejects_wrong_document_state() -> None:
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository)
    registration = service.register_document(
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"doc",
    )
    workflow = EvidenceValidationWorkflow(
        repository=repository, validator=EvidenceValidator()
    )

    with pytest.raises(EvidenceValidationWorkflowError, match="validating"):
        workflow.run(registration.document.id, document_payload())


def test_evidence_modules_do_not_import_gemini_or_supabase() -> None:
    validator_source = evidence_validator_module.__loader__.get_source(
        evidence_validator_module.__name__
    )
    service_source = evidence_service_module.__loader__.get_source(
        evidence_service_module.__name__
    )

    assert "google.genai" not in validator_source
    assert "google.genai" not in service_source
    assert "supabase" not in validator_source.lower()
    assert "supabase" not in service_source.lower()
