"""Smoke check operativo para Supabase.

No procesa documentos ni llama Gemini. Sirve para confirmar rapidamente si la
configuracion, repositorios, Storage y publicacion vigente estan listos.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Sequence

from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository
from app.core.settings import Settings, load_settings
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.storage.errors import StorageConfigurationError


@dataclass(frozen=True)
class SupabaseHealthcheckResult:
    configuration_ok: bool
    storage_bucket_ok: bool
    processed_document_count: int
    published_run_id: str | None

    @property
    def connectivity_ok(self) -> bool:
        return self.configuration_ok and self.storage_bucket_ok

    @property
    def strict_ok(self) -> bool:
        return (
            self.connectivity_ok
            and self.processed_document_count > 0
            and self.published_run_id is not None
        )


def collect_supabase_healthcheck(
    *,
    settings: Settings | None = None,
    document_repository: Any | None = None,
    analysis_run_repository: Any | None = None,
    client: Any | None = None,
    client_factory: Any | None = None,
) -> SupabaseHealthcheckResult:
    settings = settings or load_settings()
    _validate_required_settings(settings)
    client = client or _build_client(settings, client_factory)
    document_repository = document_repository or SupabaseDocumentRepository(
        settings=settings,
        client=client,
    )
    analysis_run_repository = (
        analysis_run_repository
        or SupabaseAnalysisRunRepository(settings=settings, client=client)
    )

    storage_bucket_ok = _storage_bucket_exists(
        client,
        settings.supabase_storage_bucket,
    )
    processed_documents = document_repository.list_processed_documents()
    latest_published = analysis_run_repository.get_latest_published_run()
    return SupabaseHealthcheckResult(
        configuration_ok=True,
        storage_bucket_ok=storage_bucket_ok,
        processed_document_count=len(processed_documents),
        published_run_id=latest_published.id if latest_published is not None else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = collect_supabase_healthcheck()
    except Exception as exc:
        print(f"[ERROR] Supabase healthcheck fallo: {exc}")
        return 1

    print(f"Configuracion: {'OK' if result.configuration_ok else 'ERROR'}")
    print(f"Storage bucket: {'OK' if result.storage_bucket_ok else 'NO ENCONTRADO'}")
    print(f"Documentos processed: {result.processed_document_count}")
    print(f"Publicacion vigente: {result.published_run_id or 'NO'}")

    if args.strict and not result.strict_ok:
        print("Strict mode: FAIL")
        return 1
    print(f"Strict mode: {'OK' if args.strict else 'omitido'}")
    return 0 if result.connectivity_ok else 1


def _validate_required_settings(settings: Settings) -> None:
    if not settings.supabase_url:
        raise StorageConfigurationError("SUPABASE_URL no esta configurada.")
    if not settings.supabase_backend_key:
        raise StorageConfigurationError(
            "SUPABASE_SERVICE_ROLE_KEY o SUPABASE_KEY no esta configurada."
        )
    if not settings.supabase_storage_bucket:
        raise StorageConfigurationError("SUPABASE_STORAGE_BUCKET no esta configurado.")


def _build_client(settings: Settings, client_factory: Any | None):
    factory = client_factory or _default_client_factory
    return factory(settings.supabase_url, settings.supabase_backend_key)


def _default_client_factory(url: str, key: str):
    try:
        from supabase import create_client
    except ImportError as exc:
        raise StorageConfigurationError(
            "Instale la dependencia 'supabase' para usar el healthcheck."
        ) from exc
    return create_client(url, key)


def _storage_bucket_exists(client: Any, bucket_name: str) -> bool:
    buckets = client.storage.list_buckets()
    return any(_bucket_name(bucket) == bucket_name for bucket in buckets)


def _bucket_name(bucket: Any) -> str | None:
    if isinstance(bucket, dict):
        return bucket.get("id") or bucket.get("name")
    return getattr(bucket, "id", None) or getattr(bucket, "name", None)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica configuracion, Storage y publicacion Supabase."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falla si no hay documentos processed o publicacion vigente.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
