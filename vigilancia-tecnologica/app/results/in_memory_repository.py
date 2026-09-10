"""Repositorio en memoria para resultados normalizados."""

from __future__ import annotations

from app.results.errors import DuplicateResultError
from app.results.models import PersistenceBundle


class InMemoryResultRepository:
    """Persistencia atomica en memoria para pruebas."""

    def __init__(self) -> None:
        self._bundles: dict[str, PersistenceBundle] = {}
        self._canonical_keys: set[str] = set()

    def save_bundle(self, bundle: PersistenceBundle) -> PersistenceBundle:
        if bundle.document_id in self._bundles:
            raise DuplicateResultError(
                f"Ya existe resultado persistido para {bundle.document_id}."
            )

        keys = [record.canonical_key for record in bundle.all_records()]
        if len(keys) != len(set(keys)):
            raise DuplicateResultError("El bundle contiene canonical_key duplicada.")
        duplicated = [key for key in keys if key in self._canonical_keys]
        if duplicated:
            raise DuplicateResultError(
                f"canonical_key ya existe: {duplicated[0]}."
            )

        self._bundles[bundle.document_id] = bundle
        self._canonical_keys.update(keys)
        return bundle

    def get_bundle(self, document_id: str) -> PersistenceBundle | None:
        return self._bundles.get(document_id)

    def has_canonical_key(self, canonical_key: str) -> bool:
        return canonical_key in self._canonical_keys
