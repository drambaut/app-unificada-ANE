"""Pruebas del workflow de analisis individual."""

from __future__ import annotations

from io import BytesIO

import fitz
import pandas as pd
import pytest

from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import DocumentStatus, JobStatus, JobType, SourceType
from app.documents.service import DocumentService
from app.llm.base import LLMInput
from app.llm.service import StructuredExtractionService
from app.preparation.errors import DocumentPreparationError
from app.preparation.service import DocumentPreparationService
from app.workflows.document_analysis import DocumentAnalysisWorkflow
from app.workflows.errors import WorkflowError


def evidence() -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": "Texto fuente.",
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": "Seccion",
        "confidence": "Alta",
    }


def document_payload(confidence: str = "Alta") -> dict:
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
        "evidence": [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [],
        "objectives": [],
        "activities": [],
        "regulatory_agenda_initiatives": [],
        "regulatory_agenda_deliverables": [],
        "evidence": [],
    }


def policy_payload() -> dict:
    return {
        "policies": [],
        "activities": [],
        "commitments": [],
        "evidence": [],
    }


class FakeLLMClient:
    model_name = "fake-model"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def generate_json(
        self, *, prompt: str, input_data: LLMInput, response_schema: dict
    ) -> dict:
        self.calls.append(
            {
                "prompt": prompt,
                "input_data": input_data,
                "response_schema": response_schema,
            }
        )
        return self.payload


class FailingPreparer:
    def prepare(self, *, document_id: str, file_name: str, content: bytes):
        raise DocumentPreparationError("preparacion fallida")


def make_pdf_bytes(texts: list[str]) -> bytes:
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        page.insert_text((72, 72), text)
    output = document.tobytes()
    document.close()
    return output


def make_excel_bytes() -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame({"policy": ["A"], "owner": ["Area 1"]}).to_excel(
            writer, sheet_name="Policies", index=False
        )
        pd.DataFrame({"commitment": ["C"]}).to_excel(
            writer, sheet_name="Commitments", index=False
        )
    return output.getvalue()


def make_workflow(
    payload: dict,
    *,
    preparers: dict | None = None,
) -> tuple[
    DocumentAnalysisWorkflow,
    DocumentService,
    InMemoryDocumentRepository,
    FakeLLMClient,
]:
    repository = InMemoryDocumentRepository()
    document_service = DocumentService(repository)
    preparation_service = DocumentPreparationService(repository, preparers=preparers)
    llm_client = FakeLLMClient(payload)
    extraction_service = StructuredExtractionService(client=llm_client)
    workflow = DocumentAnalysisWorkflow(
        document_service=document_service,
        preparation_service=preparation_service,
        extraction_service=extraction_service,
        repository=repository,
    )
    return workflow, document_service, repository, llm_client


def register(
    document_service: DocumentService,
    *,
    file_name: str,
    file_type: str,
    source_type: SourceType,
    content: bytes,
) -> str:
    registration = document_service.register_document(
        file_name=file_name,
        file_type=file_type,
        source_type=source_type,
        content=content,
        storage_path=f"storage/{file_name}",
    )
    return registration.document.id


def test_complete_pdf_surveillance_flow_keeps_original_bytes() -> None:
    pdf_bytes = make_pdf_bytes(["Texto suficiente para preparar y analizar."])
    workflow, document_service, repository, llm_client = make_workflow(document_payload())
    document_id = register(
        document_service,
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=pdf_bytes,
    )

    result = workflow.run(document_id, pdf_bytes, metadata={"origin": "test"})

    assert result.document.status == DocumentStatus.VALIDATING
    assert result.preparation_job.status == JobStatus.COMPLETED
    assert result.analysis_job.job_type == JobType.DOCUMENT_ANALYSIS
    assert result.analysis_job.status == JobStatus.COMPLETED
    assert result.evidence_validation_job.job_type == JobType.EVIDENCE_VALIDATION
    assert result.evidence_validation_job.status == JobStatus.QUEUED
    assert result.chunks[0].page_number == 1
    input_data = llm_client.calls[0]["input_data"]
    assert input_data.file_bytes is pdf_bytes
    assert input_data.mime_type == "application/pdf"
    assert input_data.metadata["origin"] == "test"
    assert len(repository.list_jobs(document_id)) == 3


def test_complete_excel_policy_matrix_flow_uses_text_chunks_only() -> None:
    excel_bytes = make_excel_bytes()
    workflow, document_service, _repository, llm_client = make_workflow(policy_payload())
    document_id = register(
        document_service,
        file_name="matrix.xlsx",
        file_type="xlsx",
        source_type=SourceType.POLICY_MATRIX,
        content=excel_bytes,
    )

    result = workflow.run(document_id, excel_bytes)

    assert result.document.status == DocumentStatus.VALIDATING
    assert result.analysis_job.job_type == JobType.POLICY_MATRIX_ANALYSIS
    assert result.extraction_result.prompt_id == "policy_matrix_extraction"
    input_data = llm_client.calls[0]["input_data"]
    assert input_data.file_bytes is None
    assert "=== SHEET: Policies ===" in input_data.text
    assert "=== SHEET: Commitments ===" in input_data.text
    assert "ROW_REFERENCE: 2" in input_data.text


def test_institutional_plan_uses_its_prompt_and_contract() -> None:
    pdf_bytes = make_pdf_bytes(["Documento institucional con texto suficiente."])
    workflow, document_service, _repository, llm_client = make_workflow(
        institutional_payload()
    )
    document_id = register(
        document_service,
        file_name="plan.pdf",
        file_type="pdf",
        source_type=SourceType.INSTITUTIONAL_PLAN,
        content=pdf_bytes,
    )

    result = workflow.run(document_id, pdf_bytes)

    assert result.analysis_job.job_type == JobType.INSTITUTIONAL_PLAN_ANALYSIS
    assert result.extraction_result.prompt_id == "institutional_plan_extraction"
    assert result.extraction_result.contract_name == "InstitutionalPlanExtraction"
    assert llm_client.calls[0]["response_schema"]["title"] == "InstitutionalPlanExtraction"


def test_invalid_result_marks_document_and_analysis_job_failed() -> None:
    pdf_bytes = make_pdf_bytes(["Texto suficiente para preparar y fallar luego."])
    workflow, document_service, repository, _llm_client = make_workflow(
        document_payload(confidence="Muy alta")
    )
    document_id = register(
        document_service,
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=pdf_bytes,
    )

    with pytest.raises(WorkflowError, match="analysis"):
        workflow.run(document_id, pdf_bytes)

    assert repository.get_document(document_id).status == DocumentStatus.FAILED
    analysis_jobs = [
        job for job in repository.list_jobs(document_id)
        if job.job_type == JobType.DOCUMENT_ANALYSIS
    ]
    assert analysis_jobs[0].status == JobStatus.FAILED


def test_preparation_error_marks_failed() -> None:
    workflow, document_service, repository, _llm_client = make_workflow(
        document_payload(), preparers={".pdf": FailingPreparer()}
    )
    document_id = register(
        document_service,
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=b"pdf",
    )

    with pytest.raises(WorkflowError, match="preparation"):
        workflow.run(document_id, b"pdf")

    assert repository.get_document(document_id).status == DocumentStatus.FAILED
    prep_job = repository.list_jobs(document_id)[0]
    assert prep_job.status == JobStatus.FAILED
    assert prep_job.error_message == "preparacion fallida"


def test_missing_document_fails_before_any_call() -> None:
    workflow, _document_service, repository, llm_client = make_workflow(document_payload())

    with pytest.raises(WorkflowError, match="document_lookup"):
        workflow.run("no-existe", b"bytes")

    assert repository.list_jobs("no-existe") == []
    assert llm_client.calls == []


def test_failed_document_is_not_analyzed() -> None:
    pdf_bytes = make_pdf_bytes(["Texto suficiente para registrar."])
    workflow, document_service, repository, llm_client = make_workflow(document_payload())
    document_id = register(
        document_service,
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=pdf_bytes,
    )
    repository.update_document_status(document_id, DocumentStatus.FAILED)

    with pytest.raises(WorkflowError, match="failed"):
        workflow.run(document_id, pdf_bytes)

    assert llm_client.calls == []


def test_rerun_does_not_duplicate_jobs() -> None:
    pdf_bytes = make_pdf_bytes(["Texto suficiente para preparar una vez."])
    workflow, document_service, repository, _llm_client = make_workflow(document_payload())
    document_id = register(
        document_service,
        file_name="doc.pdf",
        file_type="pdf",
        source_type=SourceType.SURVEILLANCE,
        content=pdf_bytes,
    )

    workflow.run(document_id, pdf_bytes)

    with pytest.raises(WorkflowError, match="uploaded"):
        workflow.run(document_id, pdf_bytes)

    assert [job.job_type for job in repository.list_jobs(document_id)] == [
        JobType.DOCUMENT_PREPARATION,
        JobType.DOCUMENT_ANALYSIS,
        JobType.EVIDENCE_VALIDATION,
    ]
