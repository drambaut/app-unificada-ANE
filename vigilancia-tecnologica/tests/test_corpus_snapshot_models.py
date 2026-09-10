"""Pruebas de modelos e interfaces de instantaneas del corpus."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime

import pytest

from app.corpus_snapshots.errors import (
    InvalidCorpusSnapshotError,
    InvalidSnapshotReferenceError,
)
from app.corpus_snapshots.models import CorpusSnapshot, PromptContext, SnapshotRecordRef
from app.corpus_snapshots.repository import CorpusSnapshotRepository


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def record_ref(
    record_id: str = "finding-1",
    *,
    document_id: str = "doc-1",
    record_type: str = "finding",
    canonical_key: str = "finding|doc-1|tema|riesgo",
    content_hash: str = "hash-1",
    record_version: str = "v1",
) -> SnapshotRecordRef:
    return SnapshotRecordRef(
        record_id=record_id,
        document_id=document_id,
        record_type=record_type,
        canonical_key=canonical_key,
        content_hash=content_hash,
        record_version=record_version,
        created_at=NOW,
    )


def snapshot(**overrides) -> CorpusSnapshot:
    values = {
        "id": "snapshot-1",
        "created_at": NOW,
        "snapshot_hash": "snapshot-hash",
        "selection_criteria": {"status": "processed", "until": "2026-01-01"},
        "surveillance_document_ids": ("doc-b", "doc-a"),
        "institutional_plan_document_ids": ("plan-1",),
        "policy_matrix_document_ids": ("matrix-1",),
        "record_refs": (
            record_ref("record-b", document_id="doc-b"),
            record_ref("record-a", document_id="doc-a"),
        ),
        "metadata": {"created_by": "test"},
    }
    values.update(overrides)
    return CorpusSnapshot(**values)


def test_snapshot_models_are_frozen():
    item = record_ref()
    snap = snapshot()
    context = PromptContext(
        snapshot_id=snap.id,
        prompt_id="thematic_landscape",
        prompt_version="v1",
        payload={"findings": []},
        included_ids=("finding-1",),
        omitted_counts={},
        context_hash="context-hash",
    )

    with pytest.raises(FrozenInstanceError):
        item.record_id = "other"
    with pytest.raises(FrozenInstanceError):
        snap.id = "other"
    with pytest.raises(FrozenInstanceError):
        context.prompt_id = "other"


def test_internal_dictionaries_are_deeply_immutable_and_defensive():
    criteria = {"status": "processed"}
    metadata = {"owner": "ane"}
    payload = {"items": [{"id": "a"}]}
    omitted = {"findings": 0}

    snap = snapshot(selection_criteria=criteria, metadata=metadata)
    context = PromptContext(
        snapshot_id="snapshot-1",
        prompt_id="thematic_landscape",
        prompt_version="v1",
        payload=payload,
        included_ids=("a",),
        omitted_counts=omitted,
        context_hash="context-hash",
    )

    criteria["status"] = "mutated"
    metadata["owner"] = "mutated"
    payload["items"][0]["id"] = "mutated"
    omitted["findings"] = 99

    assert snap.selection_criteria["status"] == "processed"
    assert snap.metadata["owner"] == "ane"
    assert context.payload["items"][0]["id"] == "a"
    assert context.omitted_counts["findings"] == 0

    with pytest.raises(TypeError):
        snap.selection_criteria["status"] = "mutated"
    with pytest.raises(TypeError):
        context.payload["items"][0]["id"] = "mutated"


def test_ids_and_references_are_sorted_deterministically():
    snap = snapshot(
        surveillance_document_ids=("doc-c", "doc-a", "doc-b"),
        record_refs=(
            record_ref("r-2", document_id="doc-b", record_type="evidence"),
            record_ref("r-1", document_id="doc-a", record_type="finding"),
            record_ref("r-3", document_id="doc-a", record_type="document_analysis"),
        ),
    )
    context = PromptContext(
        snapshot_id=snap.id,
        prompt_id="thematic_landscape",
        prompt_version="v1",
        payload={"b": 2, "a": 1},
        included_ids=("id-b", "id-a"),
        omitted_counts={"z": 0, "a": 0},
        context_hash="context-hash",
    )

    assert snap.surveillance_document_ids == ("doc-a", "doc-b", "doc-c")
    assert [ref.record_id for ref in snap.record_refs] == ["r-3", "r-2", "r-1"]
    assert tuple(context.payload.keys()) == ("a", "b")
    assert context.included_ids == ("id-a", "id-b")
    assert tuple(context.omitted_counts.keys()) == ("a", "z")


def test_references_require_hash_and_version():
    item = record_ref(content_hash="hash-1", record_version="v1")

    assert item.content_hash == "hash-1"
    assert item.record_version == "v1"

    with pytest.raises(InvalidSnapshotReferenceError, match="content_hash"):
        record_ref(content_hash="")
    with pytest.raises(InvalidSnapshotReferenceError, match="record_version"):
        record_ref(record_version="")


@pytest.mark.parametrize(
    "field_name",
    [
        "record_id",
        "document_id",
        "record_type",
        "canonical_key",
    ],
)
def test_rejects_empty_reference_identifiers(field_name):
    values = {
        "record_id": "record-1",
        "document_id": "doc-1",
        "record_type": "finding",
        "canonical_key": "key",
        "content_hash": "hash",
        "record_version": "v1",
    }
    values[field_name] = ""

    with pytest.raises(InvalidSnapshotReferenceError, match=field_name):
        record_ref(**values)


def test_rejects_empty_snapshot_and_context_ids():
    with pytest.raises(InvalidCorpusSnapshotError, match="id"):
        snapshot(id="")
    with pytest.raises(InvalidCorpusSnapshotError, match="snapshot_hash"):
        snapshot(snapshot_hash="")
    with pytest.raises(InvalidCorpusSnapshotError, match="IDs"):
        snapshot(surveillance_document_ids=("doc-1", ""))
    with pytest.raises(InvalidCorpusSnapshotError, match="context_hash"):
        PromptContext(
            snapshot_id="snapshot-1",
            prompt_id="thematic_landscape",
            prompt_version="v1",
            payload={},
            included_ids=(),
            omitted_counts={},
            context_hash="",
        )


def test_repository_protocol_exposes_append_only_interface():
    assert hasattr(CorpusSnapshotRepository, "save_snapshot")
    assert hasattr(CorpusSnapshotRepository, "get_snapshot")
    assert hasattr(CorpusSnapshotRepository, "list_snapshots")
    assert not hasattr(CorpusSnapshotRepository, "update_snapshot")


def test_deterministic_comparison_and_asdict_serialization():
    first = snapshot(
        selection_criteria={"b": "2", "a": "1"},
        surveillance_document_ids=("doc-b", "doc-a"),
    )
    second = snapshot(
        selection_criteria={"a": "1", "b": "2"},
        surveillance_document_ids=("doc-a", "doc-b"),
    )

    assert first == second
    assert asdict(first)["surveillance_document_ids"] == ("doc-a", "doc-b")
    assert dict(first.selection_criteria) == {"a": "1", "b": "2"}
