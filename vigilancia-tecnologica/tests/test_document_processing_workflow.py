"""Pruebas end-to-end del workflow integral individual."""

from __future__ import annotations

import copy
from io import BytesIO

import fitz
import pandas as pd
import pytest

import app.workflows.document_processing as processing_module
from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import DocumentStatus, JobStatus, JobType, SourceType
from app.documents.service import DocumentService
from app.evidence.service import EvidenceValidationWorkflow
from app.evidence.validator import EvidenceValidator
from app.llm.base import LLMInput
from app.llm.service import StructuredExtractionService
from app.preparation.errors import DocumentPreparationError
from app.preparation.service import DocumentPreparationService
from app.results.in_memory_repository import InMemoryResultRepository
from app.results.normalizer import ResultNormalizer
from app.results.service import ResultPersistenceService
from app.workflows.document_analysis import DocumentAnalysisWorkflow
from app.workflows.document_processing import (
    DocumentProcessingWorkflow,
    DocumentProcessingWorkflowError,
)


PDF_TEXT = "Texto fuente verificable para vigilancia."
PLAN_TEXT = "Texto fuente verificable para plan institucional."
EXCEL_QUOTE = "policy=A"


class FakeLLMClient:
    model_name = "fake-model"

    def __init__(self, payload_by_prompt: dict[str, dict]) -> None:
        self.payload_by_prompt = payload_by_prompt
        self.calls: list[dict] = []

    def generate_json(
        self, *, prompt: str, input_data: LLMInput, response_schema: dict
    ) -> dict:
        prompt_id = {
            "DocumentExtraction": "document_extraction",
            "InstitutionalPlanExtraction": "institutional_plan_extraction",
            "PolicyMatrixExtraction": "policy_matrix_extraction",
        }[response_schema["title"]]
        self.calls.append(
            {
                "prompt_id": prompt_id,
                "input_data": input_data,
                "response_schema": response_schema,
            }
        )
        return copy.deepcopy(self.payload_by_prompt[prompt_id])


class FailingPreparer:
    def prepare(self, *, document_id: str, file_name: str, content: bytes):
        raise DocumentPreparationError("fallo de preparacion")


class FailingResultRepository(InMemoryResultRepository):
    def save_bundle(self, bundle):
        raise RuntimeError("fallo atomico")


def make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def make_excel_bytes() -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame({"policy": ["A"], "owner": ["Area 1"]}).to_excel(
            writer, sheet_name="Policies", index=False
        )
    return output.getvalue()


def evidence(quote: str, *, page_number=1, sheet_name=None, row_reference=None) -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": quote,
        "evidence_type": "cita_textual",
        "page_number": page_number,
        "sheet_name": sheet_name,
        "row_reference": row_reference,
        "section_title": None,
        "confidence": "Alta",
    }


def document_payload(quote: str = PDF_TEXT, confidence: str = "Alta") -> dict:
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
                "finding_type": "estudio_o_evidencia",
                "title": "Hallazgo",
                "description": "Descripcion",
                "preliminary_topics": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
                "confidence": confidence,
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence(quote)],
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
                "period": "2026",
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
        "evidence": [evidence(PLAN_TEXT)],
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
                "temporary_id": "activity-1",
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
        "commitments": [],
        "evidence": [
            evidence(
                EXCEL_QUOTE,
                page_number=None,
                sheet_name="Policies",
                row_reference="2",
            )
        ],
    }


def uuid_factory():
    counter = {"value": 0}

    def next_uuid() -> str:
        counter["value"] += 1
        return f"uuid-{counter['value']}"

    return next_uuid


def build_workflow(
    payloads: dict[str, dict] | None = None,
    *,
    preparers: dict | None = None,
    result_repository=None,
):
    document_repository = InMemoryDocumentRepository()
    result_repository = result_repository or InMemoryResultRepository()
    document_service = DocumentService(document_repository)
    preparation_service = DocumentPreparationService(
        document_repository, preparers=preparers
    )
    llm_client = FakeLLMClient(
        payloads
        or {
            "document_extraction": document_payload(),
            "institutional_plan_extraction": institutional_payload(),
            "policy_matrix_extraction": policy_payload(),
        }
    )
    extraction_service = StructuredExtractionService(client=llm_client)
    analysis_workflow = DocumentAnalysisWorkflow(
        document_service=document_service,
        preparation_service=preparation_service,
        extraction_service=extraction_service,
        repository=document_repository,
    )
    evidence_workflow = EvidenceValidationWorkflow(
        repository=document_repository,
        validator=EvidenceValidator(),
    )
    persistence_service = ResultPersistenceService(
        document_repository=document_repository,
        result_repository=result_repository,
        normalizer=ResultNormalizer(uuid_factory=uuid_factory()),
    )
    workflow = DocumentProcessingWorkflow(
        document_service=document_service,
        analysis_workflow=analysis_workflow,
        evidence_workflow=evidence_workflow,
        persistence_service=persistence_service,
        document_repository=document_repository,
        result_repository=result_repository,
    )
    return workflow, document_repository, result_repository, llm_client


def test_pdf_surveillance_finishes_processed() -> None:
    workflow, _documents, results, llm = build_workflow()

    result = workflow.run(
        file_name="doc.pdf",
        file_bytes=make_pdf_bytes(PDF_TEXT),
        source_type=SourceType.SURVEILLANCE,
        metadata={"origin": "test"},
    )

    assert result.document.status == DocumentStatus.PROCESSED
    assert result.extraction_result.prompt_id == "document_extraction"
    assert result.evidence_report.is_valid is True
    assert results.get_bundle(result.document.id) == result.persistence_bundle
    assert [job.status for job in result.jobs] == [JobStatus.COMPLETED] * 4
    assert [job.job_type for job in result.jobs] == [
        JobType.DOCUMENT_PREPARATION,
        JobType.DOCUMENT_ANALYSIS,
        JobType.EVIDENCE_VALIDATION,
        JobType.RESULT_PERSISTENCE,
    ]
    assert llm.calls[0]["input_data"].file_bytes is not None
    assert llm.calls[0]["input_data"].mime_type == "application/pdf"


def test_pdf_institutional_plan_finishes_processed() -> None:
    workflow, _documents, _results, llm = build_workflow()

    result = workflow.run(
        file_name="plan.pdf",
        file_bytes=make_pdf_bytes(PLAN_TEXT),
        source_type=SourceType.INSTITUTIONAL_PLAN,
    )

    assert result.document.status == DocumentStatus.PROCESSED
    assert result.extraction_result.prompt_id == "institutional_plan_extraction"
    assert result.extraction_result.contract_name == "InstitutionalPlanExtraction"
    assert llm.calls[0]["response_schema"]["title"] == "InstitutionalPlanExtraction"


def test_excel_policy_matrix_finishes_processed_with_text_input() -> None:
    workflow, _documents, _results, llm = build_workflow()

    result = workflow.run(
        file_name="matrix.xlsx",
        file_bytes=make_excel_bytes(),
        source_type=SourceType.POLICY_MATRIX,
    )

    assert result.document.status == DocumentStatus.PROCESSED
    assert result.extraction_result.prompt_id == "policy_matrix_extraction"
    assert result.persistence_bundle.policy_activities[0].data["policy_id"] == (
        result.persistence_bundle.policies[0].id
    )
    assert llm.calls[0]["input_data"].file_bytes is None
    assert "=== SHEET: Policies ===" in llm.calls[0]["input_data"].text
    assert "ROW_REFERENCE: 2" in llm.calls[0]["input_data"].text


def test_uuid_relations_and_evidence_are_persisted() -> None:
    workflow, _documents, _results, _llm = build_workflow()

    result = workflow.run(
        file_name="doc.pdf",
        file_bytes=make_pdf_bytes(PDF_TEXT),
        source_type=SourceType.SURVEILLANCE,
    )

    finding = result.persistence_bundle.findings[0]
    evidence_record = result.persistence_bundle.evidence[0]
    assert finding.data["evidence_ids"] == [evidence_record.id]
    assert evidence_record.data["matched_chunk_id"] == result.chunks[0].id
    assert "temporary_id" not in finding.data


def test_duplicate_is_rejected_before_llm() -> None:
    workflow, document_repository, _results, llm = build_workflow()
    file_bytes = make_pdf_bytes(PDF_TEXT)

    workflow.run(
        file_name="doc.pdf",
        file_bytes=file_bytes,
        source_type=SourceType.SURVEILLANCE,
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=file_bytes,
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "registration"
    assert len(llm.calls) == 1
    assert len(document_repository.list_jobs(exc_info.value.document_id)) == 4


def test_preparation_error_stops_flow() -> None:
    workflow, document_repository, results, llm = build_workflow(
        preparers={".pdf": FailingPreparer()}
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=make_pdf_bytes(PDF_TEXT),
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "analysis"
    assert document_repository.get_document(exc_info.value.document_id).status == DocumentStatus.FAILED
    assert results.get_bundle(exc_info.value.document_id) is None
    assert llm.calls == []


def test_invalid_llm_response_stops_flow() -> None:
    workflow, document_repository, results, _llm = build_workflow(
        {"document_extraction": document_payload(confidence="Muy alta")}
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=make_pdf_bytes(PDF_TEXT),
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "analysis"
    assert document_repository.get_document(exc_info.value.document_id).status == DocumentStatus.FAILED
    assert results.get_bundle(exc_info.value.document_id) is None


def test_invalid_evidence_prevents_persistence() -> None:
    workflow, document_repository, results, _llm = build_workflow(
        {"document_extraction": document_payload(quote="cita inexistente")}
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=make_pdf_bytes(PDF_TEXT),
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "evidence_validation"
    assert document_repository.get_document(exc_info.value.document_id).status == DocumentStatus.FAILED
    assert results.get_bundle(exc_info.value.document_id) is None


def test_persistence_error_does_not_save_partially() -> None:
    failing_results = FailingResultRepository()
    workflow, document_repository, _results, _llm = build_workflow(
        result_repository=failing_results
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=make_pdf_bytes(PDF_TEXT),
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "result_persistence"
    assert document_repository.get_document(exc_info.value.document_id).status == DocumentStatus.FAILED
    assert failing_results.get_bundle(exc_info.value.document_id) is None


def test_payload_original_is_not_modified() -> None:
    payload = document_payload()
    original = copy.deepcopy(payload)
    workflow, _documents, _results, _llm = build_workflow(
        {"document_extraction": payload}
    )

    workflow.run(
        file_name="doc.pdf",
        file_bytes=make_pdf_bytes(PDF_TEXT),
        source_type=SourceType.SURVEILLANCE,
    )

    assert payload == original


def test_file_bytes_do_not_appear_in_error_message() -> None:
    secret_bytes = b"SUPER_SECRET_BYTES"
    workflow, _documents, _results, _llm = build_workflow(
        preparers={".pdf": FailingPreparer()}
    )

    with pytest.raises(DocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=secret_bytes,
            source_type=SourceType.SURVEILLANCE,
        )

    assert "SUPER_SECRET_BYTES" not in str(exc_info.value)


def test_processing_module_does_not_import_gemini_or_supabase() -> None:
    source = processing_module.__loader__.get_source(processing_module.__name__)

    assert "google.genai" not in source
    assert "supabase" not in source.lower()
