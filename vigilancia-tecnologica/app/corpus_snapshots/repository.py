"""Contrato de persistencia para instantaneas del corpus."""

from __future__ import annotations

from typing import Protocol

from app.corpus_snapshots.models import CorpusSnapshot


class CorpusSnapshotRepository(Protocol):
    """Repositorio append-only para instantaneas inmutables.

    No existe update_snapshot: guardar dos veces el mismo ID debe rechazarse y
    una instantanea guardada no puede reemplazarse.
    """

    def save_snapshot(self, snapshot: CorpusSnapshot) -> CorpusSnapshot:
        """Guarda una instantanea nueva sin reemplazar una existente."""

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None:
        """Obtiene una instantanea por ID."""

    def list_snapshots(self) -> list[CorpusSnapshot]:
        """Lista las instantaneas disponibles."""

