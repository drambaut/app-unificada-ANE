"""Repositorio Supabase para snapshots inmutables del corpus."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from app.core.settings import Settings, load_settings
from app.corpus_snapshots.errors import DuplicateCorpusSnapshotError
from app.corpus_snapshots.models import CorpusSnapshot, SnapshotRecordRef
from app.storage.errors import StorageConfigurationError


class SupabaseCorpusSnapshotRepository:
    """Implementacion append-only del contrato `CorpusSnapshotRepository`."""

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

    def save_snapshot(self, snapshot: CorpusSnapshot) -> CorpusSnapshot:
        if self.get_snapshot(snapshot.id) is not None:
            raise DuplicateCorpusSnapshotError(
                f"Ya existe una instantanea con ID {snapshot.id}."
            )
        existing_snapshot = self.get_snapshot_by_hash(snapshot.snapshot_hash)
        if existing_snapshot is not None:
            return existing_snapshot

        self._insert(
            "corpus_snapshots",
            {
                "id": snapshot.id,
                "created_at": snapshot.created_at.isoformat(),
                "snapshot_hash": snapshot.snapshot_hash,
                "selection_criteria": _plain(snapshot.selection_criteria),
                "metadata": _plain(snapshot.metadata),
            },
        )
        for document_id in snapshot.surveillance_document_ids:
            self._insert_snapshot_document(snapshot.id, document_id, "surveillance")
        for document_id in snapshot.institutional_plan_document_ids:
            self._insert_snapshot_document(
                snapshot.id, document_id, "institutional_plan"
            )
        for document_id in snapshot.policy_matrix_document_ids:
            self._insert_snapshot_document(snapshot.id, document_id, "policy_matrix")
        for record_ref in snapshot.record_refs:
            self._insert(
                "corpus_snapshot_record_refs",
                {
                    "snapshot_id": snapshot.id,
                    "record_id": record_ref.record_id,
                    "document_id": record_ref.document_id,
                    "record_type": record_ref.record_type,
                    "canonical_key": record_ref.canonical_key,
                    "content_hash": record_ref.content_hash,
                    "record_version": record_ref.record_version,
                    "created_at": record_ref.created_at.isoformat(),
                },
        )
        return snapshot

    def get_snapshot_by_hash(self, snapshot_hash: str) -> CorpusSnapshot | None:
        row = _single(
            self._table("corpus_snapshots")
            .select("*")
            .eq("snapshot_hash", snapshot_hash)
            .limit(1)
            .execute()
            .data
        )
        if row is None:
            return None
        return self.get_snapshot(row["id"])

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None:
        row = _single(
            self._table("corpus_snapshots")
            .select("*")
            .eq("id", snapshot_id)
            .limit(1)
            .execute()
            .data
        )
        if row is None:
            return None
        document_rows = (
            self._table("corpus_snapshot_documents")
            .select("*")
            .eq("snapshot_id", snapshot_id)
            .execute()
            .data
            or []
        )
        ref_rows = (
            self._table("corpus_snapshot_record_refs")
            .select("*")
            .eq("snapshot_id", snapshot_id)
            .order("record_type")
            .execute()
            .data
            or []
        )
        return _snapshot_from_rows(row, document_rows, ref_rows)

    def list_snapshots(self) -> list[CorpusSnapshot]:
        rows = (
            self._table("corpus_snapshots")
            .select("*")
            .order("created_at")
            .execute()
            .data
            or []
        )
        snapshots = [self.get_snapshot(row["id"]) for row in rows]
        return [snapshot for snapshot in snapshots if snapshot is not None]

    def _insert_snapshot_document(
        self, snapshot_id: str, document_id: str, source_type: str
    ) -> None:
        self._insert(
            "corpus_snapshot_documents",
            {
                "snapshot_id": snapshot_id,
                "document_id": document_id,
                "source_type": source_type,
            },
        )

    def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._table(table).insert(payload).execute().data
        return rows[0] if rows else payload

    def _table(self, name: str):
        return self._client_instance().table(name)

    def _client_instance(self):
        if self._client is not None:
            return self._client
        key = self._settings.supabase_backend_key
        if not self._settings.supabase_url or not key:
            raise StorageConfigurationError(
                "SUPABASE_URL y SUPABASE_KEY son requeridos para Supabase."
            )
        factory = self._client_factory or self._default_client_factory
        self._client = factory(self._settings.supabase_url, key)
        return self._client

    def _default_client_factory(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError as exc:
            raise StorageConfigurationError(
                "Instale la dependencia 'supabase' para usar repositorios Supabase."
            ) from exc
        return create_client(url, key)


def _snapshot_from_rows(
    row: dict[str, Any],
    document_rows: list[dict[str, Any]],
    ref_rows: list[dict[str, Any]],
) -> CorpusSnapshot:
    by_source = {
        "surveillance": [],
        "institutional_plan": [],
        "policy_matrix": [],
    }
    for document_row in document_rows:
        by_source[document_row["source_type"]].append(document_row["document_id"])

    return CorpusSnapshot(
        id=row["id"],
        created_at=_parse_datetime(row["created_at"]),
        snapshot_hash=row["snapshot_hash"],
        selection_criteria=row["selection_criteria"],
        surveillance_document_ids=tuple(by_source["surveillance"]),
        institutional_plan_document_ids=tuple(by_source["institutional_plan"]),
        policy_matrix_document_ids=tuple(by_source["policy_matrix"]),
        record_refs=tuple(_record_ref_from_row(ref_row) for ref_row in ref_rows),
        metadata=row.get("metadata") or {},
    )


def _record_ref_from_row(row: dict[str, Any]) -> SnapshotRecordRef:
    return SnapshotRecordRef(
        record_id=row["record_id"],
        document_id=row["document_id"],
        record_type=row["record_type"],
        canonical_key=row["canonical_key"],
        content_hash=row["content_hash"],
        record_version=row["record_version"],
        created_at=_parse_datetime(row["created_at"]),
    )


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(child) for child in value]
    return value


def _single(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not rows:
        return None
    return rows[0]


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
