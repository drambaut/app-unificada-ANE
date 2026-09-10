"""Pruebas del workflow manual completo."""

from __future__ import annotations

import copy

import pytest

from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import DocumentChunk, DocumentStatus, JobStatus, SourceType
from app.documents.service import DocumentService
from app.evidence.service import EvidenceValidationWorkflow
from app.evidence.validator import EvidenceValidator
from app.llm.base import LLMInput
from app.llm.service import StructuredExtractionService
from app.preparation.service import DocumentPreparationService
from app.results.in_memory_repository import InMemoryResultRepository
from app.results.normalizer import ResultNormalizer
from app.results.service import ResultPersistenceService
from app.storage.repository import StoredSourceDocument
from app.workflows.document_analysis import DocumentAnalysisWorkflow
from app.workflows.manual_processing import (
    ManualDocumentProcessingWorkflow,
    ManualDocumentProcessingWorkflowError,
)
from app.workflows.manual_upload import ManualDocumentUploadService


QUOTE = "Texto fuente verificable para vigilancia."


class FixedPreparer:
    def prepare(self, *, document_id: str, file_name: str, content: bytes):
        return [
            DocumentChunk(
                id="chunk-1",
                document_id=document_id,
                content=f"{QUOTE} Contexto adicional.",
                page_number=1,
                section_title=None,
                sheet_name=None,
                row_reference=None,
                content_hash=DocumentService.calculate_sha256(QUOTE.encode("utf-8")),
                position=1,
            )
        ]


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
        return copy.deepcopy(self.payload)


class FakeStorage:
    def __init__(self) -> None:
        self.uploads = []
        self.deleted = []

    def upload_source_document(
        self,
        *,
        source_type: str,
        document_id: str,
        file_name: str,
        content: bytes,
        content_type: str,
        upsert: bool = False,
    ) -> StoredSourceDocument:
        path = f"{source_type}/{document_id}/{file_name}"
        self.uploads.append(path)
        return StoredSourceDocument(
            bucket="source-documents",
            path=path,
            content_type=content_type,
            size_bytes=len(content),
        )

    def download_source_document(self, path: str) -> bytes:
        raise NotImplementedError

    def delete_source_document(self, path: str) -> None:
        self.deleted.append(path)


class FailingResultRepository(InMemoryResultRepository):
    def save_bundle(self, bundle):
        raise RuntimeError("fallo atomico")


def document_payload(quote: str = QUOTE) -> dict:
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
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [
            {
                "temporary_id": "ev-1",
                "quote": quote,
                "evidence_type": "cita_textual",
                "page_number": 1,
                "sheet_name": None,
                "row_reference": None,
                "section_title": None,
                "confidence": "Alta",
            }
        ],
    }


def uuid_factory():
    values = iter(["doc-1", "record-1", "record-2", "record-3"])
    return lambda: next(values)


def build_workflow(*, payload=None, result_repository=None):
    document_repository = InMemoryDocumentRepository()
    result_repository = result_repository or InMemoryResultRepository()
    document_service = DocumentService(document_repository)
    storage = FakeStorage()
    upload_service = ManualDocumentUploadService(
        document_repository=document_repository,
        document_service=document_service,
        storage=storage,
        uuid_factory=lambda: "doc-1",
    )
    preparation_service = DocumentPreparationService(
        document_repository,
        preparers={".pdf": FixedPreparer()},
    )
    llm_client = FakeLLMClient(payload or document_payload())
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
    workflow = ManualDocumentProcessingWorkflow(
        upload_service=upload_service,
        analysis_workflow=analysis_workflow,
        evidence_workflow=evidence_workflow,
        persistence_service=persistence_service,
        document_repository=document_repository,
    )
    return workflow, document_repository, result_repository, storage, llm_client


def test_manual_processing_uploads_prepares_analyzes_validates_and_persists():
    workflow, _documents, results, storage, llm = build_workflow()

    result = workflow.run(
        file_name="doc.pdf",
        file_bytes=b"%PDF",
        source_type=SourceType.SURVEILLANCE,
        metadata={"origin": "manual"},
    )

    assert result.document.status == DocumentStatus.PROCESSED
    assert result.document.storage_path == "surveillance/doc-1/doc.pdf"
    assert result.evidence_report.is_valid is True
    assert results.get_bundle("doc-1") == result.persistence_bundle
    assert storage.uploads == ["surveillance/doc-1/doc.pdf"]
    assert llm.calls[0]["input_data"].metadata["origin"] == "manual"
    assert [job.status for job in result.jobs] == [JobStatus.COMPLETED] * 4


def test_manual_processing_duplicate_stops_before_second_storage_write():
    workflow, _documents, _results, storage, llm = build_workflow()
    workflow.run(
        file_name="doc.pdf",
        file_bytes=b"%PDF",
        source_type=SourceType.SURVEILLANCE,
    )

    with pytest.raises(ManualDocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="copy.pdf",
            file_bytes=b"%PDF",
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "upload"
    assert len(storage.uploads) == 1
    assert len(llm.calls) == 1


def test_manual_processing_invalid_evidence_marks_document_failed():
    workflow, documents, results, _storage, _llm = build_workflow(
        payload=document_payload(quote="cita inexistente")
    )

    with pytest.raises(ManualDocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=b"%PDF",
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "evidence_validation"
    assert "ev-1: not_found" in str(exc_info.value)
    assert documents.get_document("doc-1").status == DocumentStatus.FAILED
    assert results.get_bundle("doc-1") is None


def test_manual_processing_persistence_error_marks_document_failed():
    workflow, documents, results, _storage, _llm = build_workflow(
        result_repository=FailingResultRepository()
    )

    with pytest.raises(ManualDocumentProcessingWorkflowError) as exc_info:
        workflow.run(
            file_name="doc.pdf",
            file_bytes=b"%PDF",
            source_type=SourceType.SURVEILLANCE,
        )

    assert exc_info.value.stage == "result_persistence"
    assert documents.get_document("doc-1").status == DocumentStatus.FAILED
    assert results.get_bundle("doc-1") is None
