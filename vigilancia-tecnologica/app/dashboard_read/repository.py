"""Protocols de lectura para dashboard publicado."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.documents.models import Document
from app.results.models import PersistenceBundle


class DashboardDocumentReadRepository(Protocol):
    """Lectura de documentos incluidos en un snapshot publicado."""

    def get_documents_by_ids(self, document_ids: Sequence[str]) -> list[Document]:
        """Obtiene documentos por ID."""


class DashboardResultReadRepository(Protocol):
    """Lectura de resultados persistidos incluidos en un snapshot publicado."""

    def get_bundles_by_document_ids(
        self, document_ids: Sequence[str]
    ) -> list[PersistenceBundle]:
        """Obtiene bundles persistidos por documentos."""

