"""Modelos inmutables para instantaneas estables del corpus."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.corpus_snapshots.errors import (
    InvalidCorpusSnapshotError,
    InvalidSnapshotReferenceError,
)


class FrozenDict(Mapping):
    """Mapping inmutable con orden deterministico por clave."""

    def __init__(self, values: Mapping | None = None) -> None:
        source = values or {}
        self._data = {
            key: _freeze(value)
            for key, value in sorted(source.items(), key=lambda item: str(item[0]))
        }

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return repr(self._data)

    def __eq__(self, other) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return False


def _freeze(value):
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _sorted_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    ordered = tuple(sorted(values))
    for value in ordered:
        if not value:
            raise InvalidCorpusSnapshotError("Los IDs de documentos no pueden estar vacios.")
    return ordered


@dataclass(frozen=True)
class SnapshotRecordRef:
    record_id: str
    document_id: str
    record_type: str
    canonical_key: str
    content_hash: str
    record_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "document_id",
            "record_type",
            "canonical_key",
            "record_version",
        ):
            if not getattr(self, field_name):
                raise InvalidSnapshotReferenceError(
                    f"{field_name} no puede estar vacio."
                )
        if not self.content_hash:
            raise InvalidSnapshotReferenceError("content_hash no puede estar vacio.")

    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.record_type,
            self.document_id,
            self.record_id,
            self.canonical_key,
        )


@dataclass(frozen=True)
class CorpusSnapshot:
    """Instantanea reproducible del corpus transversal.

    snapshot_hash debe calcularse posteriormente a partir de los documentos
    incluidos, record_refs exactas, record_version, content_hash y
    selection_criteria canonizados. Este modelo solo conserva el valor ya
    calculado por el builder futuro.
    """

    id: str
    created_at: datetime
    snapshot_hash: str
    selection_criteria: Mapping[str, str]
    surveillance_document_ids: tuple[str, ...]
    institutional_plan_document_ids: tuple[str, ...]
    policy_matrix_document_ids: tuple[str, ...]
    record_refs: tuple[SnapshotRecordRef, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidCorpusSnapshotError("id no puede estar vacio.")
        if not self.snapshot_hash:
            raise InvalidCorpusSnapshotError("snapshot_hash no puede estar vacio.")
        object.__setattr__(
            self,
            "selection_criteria",
            FrozenDict(self.selection_criteria),
        )
        object.__setattr__(self, "metadata", FrozenDict(self.metadata))
        object.__setattr__(
            self,
            "surveillance_document_ids",
            _sorted_strings(self.surveillance_document_ids),
        )
        object.__setattr__(
            self,
            "institutional_plan_document_ids",
            _sorted_strings(self.institutional_plan_document_ids),
        )
        object.__setattr__(
            self,
            "policy_matrix_document_ids",
            _sorted_strings(self.policy_matrix_document_ids),
        )
        object.__setattr__(
            self,
            "record_refs",
            tuple(sorted(self.record_refs, key=lambda item: item.sort_key())),
        )


@dataclass(frozen=True)
class PromptContext:
    snapshot_id: str
    prompt_id: str
    prompt_version: str
    payload: Mapping[str, Any]
    included_ids: tuple[str, ...]
    omitted_counts: Mapping[str, int]
    context_hash: str

    def __post_init__(self) -> None:
        for field_name in ("snapshot_id", "prompt_id", "prompt_version", "context_hash"):
            if not getattr(self, field_name):
                raise InvalidCorpusSnapshotError(f"{field_name} no puede estar vacio.")
        object.__setattr__(self, "payload", FrozenDict(self.payload))
        object.__setattr__(
            self,
            "included_ids",
            _sorted_strings(self.included_ids),
        )
        object.__setattr__(self, "omitted_counts", FrozenDict(self.omitted_counts))

