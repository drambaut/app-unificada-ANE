"""Modelos inmutables del dominio documental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class SourceType(str, Enum):
    SURVEILLANCE = "surveillance"
    INSTITUTIONAL_PLAN = "institutional_plan"
    POLICY_MATRIX = "policy_matrix"
    PMGE_PROJECTS = "pmge_projects"
    TECHNOLOGY_AGENDA = "technology_agenda"
    SUPPORT_DOCUMENT = "support_document"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PREPARING = "preparing"
    PREPARED = "prepared"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    READY_TO_PERSIST = "ready_to_persist"
    PROCESSED = "processed"
    FAILED = "failed"


class JobType(str, Enum):
    DOCUMENT_PREPARATION = "document_preparation"
    DOCUMENT_ANALYSIS = "document_analysis"
    INSTITUTIONAL_PLAN_ANALYSIS = "institutional_plan_analysis"
    POLICY_MATRIX_ANALYSIS = "policy_matrix_analysis"
    EVIDENCE_VALIDATION = "evidence_validation"
    RESULT_PERSISTENCE = "result_persistence"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Document:
    id: str
    file_name: str
    file_type: str
    source_type: SourceType
    file_hash: str
    storage_path: str | None
    document_date: date | None
    status: DocumentStatus
    version: int
    replaces_id: str | None
    created_at: datetime
    updated_at: datetime
    provider: str | None = None


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    document_id: str
    content: str
    page_number: int | None
    section_title: str | None
    sheet_name: str | None
    row_reference: str | None
    content_hash: str
    position: int
    embedding: list[float] | None = None


@dataclass(frozen=True)
class ProcessingJob:
    id: str
    document_id: str
    job_type: JobType
    status: JobStatus
    prompt_id: str | None
    prompt_version: str | None
    attempts: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
