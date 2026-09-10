"""Modelos de lectura para listados e historial de snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SnapshotListItem:
    snapshot_id: str
    run_id: str | None = None
    created_at: datetime = datetime.min
    published_at: datetime | None = None
    status: str = ""
    document_count: int = 0
    is_current: bool = False
    # Campos para mostrar diferencias con el snapshot anterior
    added_documents: int = 0
    removed_documents: int = 0


@dataclass(frozen=True)
class SnapshotSummary:
    snapshot_id: str
    created_at: datetime
    document_count: int
    surveillance_count: int
    institutional_count: int
    policy_matrix_count: int
    pmge_projects_count: int
    technology_agenda_count: int
    support_document_count: int
