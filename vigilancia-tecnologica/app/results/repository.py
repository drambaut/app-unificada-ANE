"""Interfaces de persistencia abstracta para resultados."""

from __future__ import annotations

from typing import Protocol

from app.results.models import PersistenceBundle


class ResultRepository(Protocol):
    """Contrato de persistencia atomica sin conocer Supabase."""

    def save_bundle(self, bundle: PersistenceBundle) -> PersistenceBundle:
        """Guarda un bundle completo de forma atomica."""

    def get_bundle(self, document_id: str) -> PersistenceBundle | None:
        """Obtiene el bundle persistido por documento."""

    def has_canonical_key(self, canonical_key: str) -> bool:
        """Comprueba si ya existe una clave canonica."""
