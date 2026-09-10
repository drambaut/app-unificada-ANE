"""Pruebas del dominio documental modular."""

from dataclasses import replace

import pytest

from app.documents.errors import (
    DocumentNotFoundError,
    DuplicateProcessingJobError,
    InvalidDocumentStatusTransition,
    InvalidProcessingJobSequence,
)
from app.documents.in_memory_repository import InMemoryDocumentRepository
from app.documents.models import (
    DocumentChunk,
    DocumentStatus,
    JobStatus,
    JobType,
    SourceType,
)
from app.documents.service import DocumentService


def service_with_repository() -> tuple[DocumentService, InMemoryDocumentRepository]:
    repository = InMemoryDocumentRepository()
    return DocumentService(repository), repository


def register(
    service: DocumentService,
    *,
    source_type: SourceType = SourceType.SURVEILLANCE,
    file_type: str = "pdf",
    content: bytes = b"contenido",
):
    return service.register_document(
        file_name=f"documento.{file_type}",
        file_type=file_type,
        source_type=source_type,
        content=content,
        storage_path=f"storage/documento.{file_type}",
    )


def prepare_document(service: DocumentService, document_id: str) -> None:
    service.transition_document_status(document_id, DocumentStatus.PREPARING)
    service.transition_document_status(document_id, DocumentStatus.PREPARED)


def test_all_documents_start_with_document_preparation_job() -> None:
    for source_type in SourceType:
        service, _repository = service_with_repository()
        result = register(
            service,
            source_type=source_type,
            content=f"contenido-{source_type.value}".encode("utf-8"),
        )

        assert result.document.status == DocumentStatus.UPLOADED
        assert result.document.storage_path == f"storage/documento.pdf"
        assert result.job is not None
        assert result.job.job_type == JobType.DOCUMENT_PREPARATION
        assert result.job.status == JobStatus.QUEUED


def test_sha256_is_deterministic() -> None:
    content = b"mismo contenido"

    assert DocumentService.calculate_sha256(content) == DocumentService.calculate_sha256(
        content
    )
    assert DocumentService.calculate_sha256(content) != DocumentService.calculate_sha256(
        b"otro contenido"
    )


def test_duplicate_detection_by_file_hash_reuses_existing_document() -> None:
    service, repository = service_with_repository()

    first = register(service, content=b"duplicado")
    second = register(service, content=b"duplicado")

    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert second.document.id == first.document.id
    assert second.job is None
    assert repository.list_jobs(first.document.id) == [first.job]


def test_complete_pdf_flow_reaches_processed() -> None:
    service, repository = service_with_repository()
    result = register(service, file_type="pdf", content=b"%PDF")
    document_id = result.document.id

    repository.update_job_status(result.job.id, JobStatus.COMPLETED)
    prepare_document(service, document_id)
    analysis = service.create_analysis_job(
        document_id, prompt_id="document_extraction", prompt_version="v1"
    )
    service.transition_document_status(document_id, DocumentStatus.ANALYZING)
    repository.update_job_status(analysis.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.VALIDATING)
    validation = service.create_evidence_validation_job(document_id)
    repository.update_job_status(validation.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.READY_TO_PERSIST)
    persistence = service.create_result_persistence_job(document_id)
    repository.update_job_status(persistence.id, JobStatus.COMPLETED)
    processed = service.transition_document_status(document_id, DocumentStatus.PROCESSED)

    assert processed.status == DocumentStatus.PROCESSED
    assert [job.job_type for job in repository.list_jobs(document_id)] == [
        JobType.DOCUMENT_PREPARATION,
        JobType.DOCUMENT_ANALYSIS,
        JobType.EVIDENCE_VALIDATION,
        JobType.RESULT_PERSISTENCE,
    ]


def test_complete_excel_flow_reaches_processed() -> None:
    service, repository = service_with_repository()
    result = register(
        service,
        source_type=SourceType.POLICY_MATRIX,
        file_type="xlsx",
        content=b"excel",
    )
    document_id = result.document.id

    repository.update_job_status(result.job.id, JobStatus.COMPLETED)
    prepare_document(service, document_id)
    analysis = service.create_analysis_job(
        document_id, prompt_id="policy_matrix_extraction", prompt_version="v1"
    )
    service.transition_document_status(document_id, DocumentStatus.ANALYZING)
    repository.update_job_status(analysis.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.VALIDATING)
    validation = service.create_evidence_validation_job(document_id)
    repository.update_job_status(validation.id, JobStatus.COMPLETED)
    service.transition_document_status(document_id, DocumentStatus.READY_TO_PERSIST)
    persistence = service.create_result_persistence_job(document_id)
    repository.update_job_status(persistence.id, JobStatus.COMPLETED)
    processed = service.transition_document_status(document_id, DocumentStatus.PROCESSED)

    assert processed.status == DocumentStatus.PROCESSED
    assert analysis.job_type == JobType.POLICY_MATRIX_ANALYSIS


def test_pdf_chunks_keep_page_number_for_search_and_validation() -> None:
    service, repository = service_with_repository()
    result = register(service, file_type="pdf")

    chunk = DocumentChunk(
        id="pdf-page-1",
        document_id=result.document.id,
        content="Texto de pagina.",
        page_number=1,
        section_title=None,
        sheet_name=None,
        row_reference=None,
        content_hash=DocumentService.calculate_sha256(b"Texto de pagina."),
        position=1,
    )

    repository.save_chunk(chunk)

    stored = repository.list_chunks(result.document.id)[0]
    assert stored.page_number == 1
    assert stored.sheet_name is None
    assert stored.row_reference is None


def test_excel_chunks_keep_sheet_and_row_reference() -> None:
    service, repository = service_with_repository()
    result = register(service, file_type="xlsx", source_type=SourceType.POLICY_MATRIX)

    chunk = DocumentChunk(
        id="excel-row-1",
        document_id=result.document.id,
        content="Fila estructurada.",
        page_number=None,
        section_title=None,
        sheet_name="Politicas",
        row_reference="A2:F2",
        content_hash=DocumentService.calculate_sha256(b"Fila estructurada."),
        position=1,
    )

    repository.save_chunk(chunk)

    stored = repository.list_chunks(result.document.id)[0]
    assert stored.page_number is None
    assert stored.sheet_name == "Politicas"
    assert stored.row_reference == "A2:F2"


def test_analysis_job_is_selected_by_source_type() -> None:
    expected = {
        SourceType.SURVEILLANCE: JobType.DOCUMENT_ANALYSIS,
        SourceType.INSTITUTIONAL_PLAN: JobType.INSTITUTIONAL_PLAN_ANALYSIS,
        SourceType.POLICY_MATRIX: JobType.POLICY_MATRIX_ANALYSIS,
    }

    for source_type, job_type in expected.items():
        service, repository = service_with_repository()
        result = register(
            service,
            source_type=source_type,
            content=f"contenido-{source_type.value}".encode("utf-8"),
        )
        repository.update_job_status(result.job.id, JobStatus.COMPLETED)
        prepare_document(service, result.document.id)

        analysis = service.create_analysis_job(result.document.id)

        assert analysis.job_type == job_type


def test_rejects_jobs_out_of_sequence() -> None:
    service, repository = service_with_repository()
    result = register(service)

    with pytest.raises(InvalidProcessingJobSequence):
        service.create_analysis_job(result.document.id)

    repository.update_job_status(result.job.id, JobStatus.COMPLETED)
    prepare_document(service, result.document.id)
    analysis = service.create_analysis_job(result.document.id)
    service.transition_document_status(result.document.id, DocumentStatus.ANALYZING)

    with pytest.raises(InvalidProcessingJobSequence):
        service.create_evidence_validation_job(result.document.id)

    repository.update_job_status(analysis.id, JobStatus.COMPLETED)
    service.transition_document_status(result.document.id, DocumentStatus.VALIDATING)
    validation = service.create_evidence_validation_job(result.document.id)

    with pytest.raises(InvalidProcessingJobSequence):
        service.create_result_persistence_job(result.document.id)

    repository.update_job_status(validation.id, JobStatus.COMPLETED)
    service.transition_document_status(result.document.id, DocumentStatus.READY_TO_PERSIST)
    persistence = service.create_result_persistence_job(result.document.id)
    assert persistence.job_type == JobType.RESULT_PERSISTENCE


def test_rejects_duplicate_equivalent_jobs_for_same_document() -> None:
    service, repository = service_with_repository()
    result = register(service)
    repository.update_job_status(result.job.id, JobStatus.COMPLETED)
    prepare_document(service, result.document.id)

    service.create_analysis_job(result.document.id)

    with pytest.raises(DuplicateProcessingJobError):
        service.create_analysis_job(result.document.id)


def test_valid_and_invalid_document_status_transitions() -> None:
    service, _repository = service_with_repository()
    result = register(service)

    preparing = service.transition_document_status(
        result.document.id, DocumentStatus.PREPARING
    )
    prepared = service.transition_document_status(
        result.document.id, DocumentStatus.PREPARED
    )

    assert preparing.status == DocumentStatus.PREPARING
    assert prepared.status == DocumentStatus.PREPARED

    with pytest.raises(InvalidDocumentStatusTransition, match="prepared a processed"):
        service.transition_document_status(result.document.id, DocumentStatus.PROCESSED)


def test_repository_stores_chunks_in_position_order() -> None:
    service, repository = service_with_repository()
    result = register(service)

    first = DocumentChunk(
        id="chunk-1",
        document_id=result.document.id,
        content="segundo",
        page_number=2,
        section_title=None,
        sheet_name=None,
        row_reference=None,
        content_hash=DocumentService.calculate_sha256(b"segundo"),
        position=2,
    )
    second = replace(
        first,
        id="chunk-2",
        content="primero",
        content_hash=DocumentService.calculate_sha256(b"primero"),
        position=1,
    )

    repository.save_chunk(first)
    repository.save_chunk(second)

    assert [chunk.id for chunk in repository.list_chunks(result.document.id)] == [
        "chunk-2",
        "chunk-1",
    ]


def test_empty_repository_and_missing_queries() -> None:
    repository = InMemoryDocumentRepository()

    assert repository.get_document("no-existe") is None
    assert repository.find_document_by_hash("hash") is None
    assert repository.get_job("job-no-existe") is None
    assert repository.list_chunks("doc-no-existe") == []
    assert repository.list_jobs("doc-no-existe") == []

    with pytest.raises(DocumentNotFoundError):
        repository.update_document_status("no-existe", DocumentStatus.FAILED)
