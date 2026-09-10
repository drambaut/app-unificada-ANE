"""Repositorio en memoria para instantaneas del corpus."""

from __future__ import annotations

from app.corpus_snapshots.errors import DuplicateCorpusSnapshotError
from app.corpus_snapshots.models import CorpusSnapshot


class InMemoryCorpusSnapshotRepository:
    """Almacenamiento append-only de instantaneas inmutables."""

    def __init__(self) -> None:
        self._snapshots: dict[str, CorpusSnapshot] = {}

    def save_snapshot(self, snapshot: CorpusSnapshot) -> CorpusSnapshot:
        if snapshot.id in self._snapshots:
            raise DuplicateCorpusSnapshotError(
                f"Ya existe una instantanea con ID {snapshot.id}."
            )
        self._snapshots[snapshot.id] = snapshot
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> list[CorpusSnapshot]:
        return sorted(
            self._snapshots.values(),
            key=lambda snapshot: (snapshot.created_at, snapshot.id),
        )

