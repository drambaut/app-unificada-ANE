"""Contrato de Storage para documentos originales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredSourceDocument:
    bucket: str
    path: str
    content_type: str
    size_bytes: int


class SourceDocumentStorage(Protocol):
    """Puerto para guardar y recuperar originales PDF/Excel."""

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
        """Sube el archivo original y devuelve su ubicacion canonica."""

    def download_source_document(self, path: str) -> bytes:
        """Descarga un archivo original desde Storage."""

    def delete_source_document(self, path: str) -> None:
        """Elimina un archivo original desde Storage. Operacion administrativa."""

    def file_exists(self, path: str) -> bool:
        """Verifica si un archivo ya existe en Storage sin descargarlo."""

    def create_signed_url(self, path: str, expires_in_seconds: int = 3600) -> str:
        """Genera una URL firmada temporal para descarga privada del archivo."""
