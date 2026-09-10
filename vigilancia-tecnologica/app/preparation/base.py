"""Interfaces para preparadores tecnicos de documentos."""

from __future__ import annotations

from typing import Protocol

from app.documents.models import DocumentChunk


class DocumentPreparer(Protocol):
    """Convierte bytes de un documento en chunks trazables."""

    def prepare(
        self,
        *,
        document_id: str,
        file_name: str,
        content: bytes,
    ) -> list[DocumentChunk]:
        """Prepara un documento sin analisis semantico."""
