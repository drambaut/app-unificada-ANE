"""Adaptador Supabase Storage para documentos originales."""

from __future__ import annotations

from typing import Any, Callable

from app.core.settings import Settings, load_settings
from app.storage.errors import (
    StorageConfigurationError,
    StorageError,
    StorageValidationError,
)
from app.storage.repository import StoredSourceDocument


class SupabaseSourceDocumentStorage:
    """Sube, descarga y elimina originales usando Supabase Storage."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client
        self._client_factory = client_factory

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
        self._validate_content(content=content, content_type=content_type)
        path = self._settings.source_document_storage_path(
            source_type=source_type,
            document_id=document_id,
            file_name=file_name,
        )
        try:
            bucket = self._bucket()
            bucket.upload(
                path,
                content,
                file_options={
                    "content-type": content_type,
                    "upsert": str(upsert).lower(),
                },
            )
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"No fue posible subir {path} a Supabase Storage.") from exc
        return StoredSourceDocument(
            bucket=self._settings.supabase_storage_bucket,
            path=path,
            content_type=content_type,
            size_bytes=len(content),
        )

    def download_source_document(self, path: str) -> bytes:
        try:
            payload = self._bucket().download(path)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"No fue posible descargar {path} desde Supabase Storage.") from exc
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, bytearray):
            return bytes(payload)
        raise StorageError(f"Supabase Storage devolvio un contenido inesperado para {path}.")

    def delete_source_document(self, path: str) -> None:
        """Elimina un archivo original. Operacion administrativa exclusiva del backend."""
        try:
            self._bucket().remove([path])
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"No fue posible eliminar {path} de Supabase Storage.") from exc

    def file_exists(self, path: str) -> bool:
        """Verifica si un archivo ya existe en Storage sin descargarlo.

        Usa list() acotado a la ruta del archivo para evitar descargas innecesarias.
        Devuelve False ante cualquier error de conectividad o permisos.
        """
        try:
            # Supabase list() admite prefix y limit; buscamos exactamente la ruta
            # separando en folder + filename para usar el prefijo correcto.
            if "/" in path:
                prefix = path.rsplit("/", 1)[0] + "/"
                filename = path.rsplit("/", 1)[1]
            else:
                prefix = ""
                filename = path
            results = self._bucket().list(
                path=prefix,
                options={"limit": 1, "search": filename},
            )
            if isinstance(results, list):
                return any(item.get("name") == filename for item in results)
            return False
        except Exception:
            return False

    def create_signed_url(self, path: str, expires_in_seconds: int = 3600) -> str:
        """Genera una URL firmada temporal para descarga privada.

        La URL expira tras `expires_in_seconds` segundos (máximo depende de RLS).
        No expone la service role key al cliente; la URL es el único token temporal.
        """
        try:
            result = self._bucket().create_signed_url(path, expires_in_seconds)
            # La respuesta de supabase-py puede ser dict o objeto con atributo
            if isinstance(result, dict):
                url = result.get("signedUrl") or result.get("signedURL") or result.get("signed_url")
            else:
                url = getattr(result, "signed_url", None) or getattr(result, "signedUrl", None)
            if not url:
                raise StorageError(f"Supabase no devolvio URL firmada para {path}.")
            return str(url)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"No fue posible crear URL firmada para {path}.") from exc

    def _bucket(self):
        return self._client_instance().storage.from_(
            self._settings.supabase_storage_bucket
        )

    def _client_instance(self):
        if self._client is not None:
            return self._client
        key = self._settings.supabase_backend_key
        if not self._settings.supabase_url or not key:
            raise StorageConfigurationError(
                "SUPABASE_URL y SUPABASE_KEY son requeridos para Supabase Storage."
            )
        factory = self._client_factory or self._default_client_factory
        self._client = factory(self._settings.supabase_url, key)
        return self._client

    def _default_client_factory(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError as exc:
            raise StorageConfigurationError(
                "Instale la dependencia 'supabase' para usar Supabase Storage."
            ) from exc
        return create_client(url, key)

    def _validate_content(self, *, content: bytes, content_type: str) -> None:
        if not content:
            raise StorageValidationError("El archivo no puede estar vacio.")
        if content_type not in self._settings.storage_allowed_mime_types:
            raise StorageValidationError(
                f"Content-Type no permitido para Storage: {content_type}."
            )
        if len(content) > self._settings.storage_file_size_limit_bytes:
            raise StorageValidationError(
                "El archivo supera el limite configurado para Storage."
            )
