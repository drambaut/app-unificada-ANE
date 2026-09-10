"""Repositorios Supabase de solo lectura para el dashboard publicado."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from app.core.settings import Settings
from app.corpus_snapshots.snapshot_read_model import SnapshotListItem
from app.documents.models import Document
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.results.models import PersistenceBundle
from app.results.supabase_repository import SupabaseResultRepository


class SupabaseDashboardDocumentReadRepository:
    """Lectura de documentos via `SupabaseDocumentRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        document_repository: SupabaseDocumentRepository | None = None,
    ) -> None:
        self._documents = document_repository or SupabaseDocumentRepository(
            settings=settings,
            client=client,
            client_factory=client_factory,
        )

    def get_documents_by_ids(self, document_ids: Sequence[str]) -> list[Document]:
        documents: list[Document] = []
        for document_id in document_ids:
            document = self._documents.get_document(document_id)
            if document is not None:
                documents.append(document)
        return documents


class SupabaseDashboardResultReadRepository:
    """Lectura de bundles via `SupabaseResultRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        result_repository: SupabaseResultRepository | None = None,
    ) -> None:
        self._results = result_repository or SupabaseResultRepository(
            settings=settings,
            client=client,
            client_factory=client_factory,
        )

    def get_bundles_by_document_ids(
        self, document_ids: Sequence[str]
    ) -> list[PersistenceBundle]:
        bundles: list[PersistenceBundle] = []
        for document_id in document_ids:
            bundle = self._results.get_bundle(document_id)
            if bundle is not None:
                bundles.append(bundle)
        return bundles


class SupabaseSnapshotListRepository:
    """Lectura de listado e historial de snapshots."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        from app.core.settings import load_settings
        self._settings = settings or load_settings()
        self._client = client
        self._client_factory = client_factory

    def get_snapshot_history(self) -> list[SnapshotListItem]:
        client = self._client_instance()
        # Traemos todos los snapshots. Idealmente se haria un join con runs
        # pero para mantenerlo simple consultamos ambos
        snapshots_data = client.table("corpus_snapshots").select("*").order("created_at", desc=True).execute().data or []
        runs_data = client.table("analysis_runs").select("*").execute().data or []
        
        runs_by_snapshot = {}
        for run in runs_data:
            sid = run.get("corpus_snapshot_id")
            if sid:
                # Solo guardamos el más reciente/relevante si hay múltiples
                if sid not in runs_by_snapshot or run.get("status") == "published":
                    runs_by_snapshot[sid] = run

        history = []
        for snap in snapshots_data:
            sid = snap["id"]
            run = runs_by_snapshot.get(sid)
            # Para document_count podríamos contar en corpus_snapshot_documents
            # pero por ahora lo inferimos del dashboard si está publicado o lo dejamos en 0 si no se requiere exacto,
            # lo ideal es contar
            doc_count = client.table("corpus_snapshot_documents").select("document_id", count="exact").eq("snapshot_id", sid).execute().count or 0
            
            history.append(
                SnapshotListItem(
                    snapshot_id=sid,
                    run_id=run["id"] if run else None,
                    created_at=snap["created_at"],
                    published_at=run["published_at"] if run else None,
                    status=run["status"] if run else "draft",
                    document_count=doc_count,
                )
            )
            
        return history

    def _client_instance(self):
        if self._client is not None:
            return self._client
        key = self._settings.supabase_backend_key or self._settings.supabase_key
        if not self._settings.supabase_url or not key:
            raise ValueError("Falta URL o key de Supabase")
        factory = self._client_factory or self._default_client_factory
        self._client = factory(self._settings.supabase_url, key)
        return self._client

    def _default_client_factory(self, url: str, key: str):
        from supabase import create_client
        return create_client(url, key)
