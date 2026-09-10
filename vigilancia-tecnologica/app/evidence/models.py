"""Modelos inmutables para validacion de evidencia."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceValidationStatus(str, Enum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    INVALID_LOCATION = "invalid_location"
    MISSING_REFERENCE = "missing_reference"
    DUPLICATE_ID = "duplicate_id"


@dataclass(frozen=True)
class EvidenceValidationItem:
    evidence_id: str
    status: EvidenceValidationStatus
    matched_chunk_id: str | None
    message: str
    page_number: int | None
    sheet_name: str | None
    row_reference: str | None


@dataclass(frozen=True)
class EvidenceValidationReport:
    document_id: str
    items: list[EvidenceValidationItem]
    total: int
    verified_count: int
    invalid_count: int
    is_valid: bool
