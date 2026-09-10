"""Pruebas del repositorio en memoria y builder de snapshots."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.errors import (
    DuplicateCorpusSnapshotError,
    InvalidCorpusSnapshotError,
    InvalidSnapshotReferenceError,
)
from app.corpus_snapshots.in_memory_repository import InMemoryCorpusSnapshotRepository
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle, ResultRecord


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def uuid_factory():
    counter = {"value": 0}

    def next_uuid() -> str:
        counter["value"] += 1
        return f"snapshot-{counter['value']}"

    return next_uuid


def document(
    document_id: str,
    source_type: SourceType,
    *,
    status: DocumentStatus = DocumentStatus.PROCESSED,
) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type=".pdf",
        source_type=source_type,
        file_hash=f"hash-{document_id}",
        storage_path=None,
        document_date=date(2026, 1, 1),
        status=status,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def record(
    record_id: str,
    document_id: str,
    *,
    data: dict | None = None,
    canonical_key: str | None = None,
) -> ResultRecord:
    return ResultRecord(
        id=record_id,
        document_id=document_id,
        data=data or {"title": record_id},
        prompt_id="document_extraction",
        prompt_version="v1",
        contract_name="DocumentExtraction",
        model_name="fake-model",
        created_at=NOW,
        canonical_key=canonical_key or f"key|{document_id}|{record_id}",
        confidence="Alta",
        extraction_basis="explicit",
    )


def surveillance_bundle(document_id: str = "doc-surv") -> PersistenceBundle:
    return PersistenceBundle(
        document_id=document_id,
        document_analysis=record("analysis-1", document_id),
        findings=[record("finding-1", document_id)],
        evidence=[record("evidence-1", document_id)],
    )


def institutional_bundle(document_id: str = "doc-plan") -> PersistenceBundle:
    return PersistenceBundle(
        document_id=document_id,
        pmge_projects=[record("project-1", document_id)],
        pmge_objectives=[record("objective-1", document_id)],
        pmge_activities=[record("activity-1", document_id)],
        regulatory_agenda_initiatives=[record("initiative-1", document_id)],
        regulatory_deliverables=[record("deliverable-1", document_id)],
        evidence=[record("evidence-plan-1", document_id)],
    )


def policy_bundle(document_id: str = "doc-policy") -> PersistenceBundle:
    return PersistenceBundle(
        document_id=document_id,
        policies=[record("policy-1", document_id)],
        policy_activities=[record("policy-activity-1", document_id)],
        policy_commitments=[record("commitment-1", document_id)],
        evidence=[record("evidence-policy-1", document_id)],
    )


def make_builder(repository=None):
    repo = repository or InMemoryCorpusSnapshotRepository()
    return CorpusSnapshotBuilder(
        repo,
        uuid_factory=uuid_factory(),
        clock=lambda: NOW,
    ), repo


def test_builds_snapshot_with_three_sources_and_saves_it():
    builder, repo = make_builder()
    docs = [
        document("doc-surv", SourceType.SURVEILLANCE),
        document("doc-plan", SourceType.INSTITUTIONAL_PLAN),
        document("doc-policy", SourceType.POLICY_MATRIX),
    ]
    bundles = [surveillance_bundle(), institutional_bundle(), policy_bundle()]

    snapshot = builder.build_snapshot(
        documents=docs,
        bundles=bundles,
        selection_criteria={"status": "processed"},
        metadata={"owner": "ane"},
    )

    assert snapshot.id == "snapshot-1"
    assert snapshot.surveillance_document_ids == ("doc-surv",)
    assert snapshot.institutional_plan_document_ids == ("doc-plan",)
    assert snapshot.policy_matrix_document_ids == ("doc-policy",)
    assert repo.get_snapshot(snapshot.id) == snapshot
    assert len(snapshot.record_refs) == 13


def test_excludes_non_processed_documents():
    builder, _ = make_builder()
    snapshot = builder.build_snapshot(
        documents=[
            document("doc-surv", SourceType.SURVEILLANCE),
            document("draft", SourceType.SURVEILLANCE, status=DocumentStatus.PREPARED),
        ],
        bundles=[surveillance_bundle("doc-surv")],
    )

    assert snapshot.surveillance_document_ids == ("doc-surv",)
    assert "draft" not in [ref.document_id for ref in snapshot.record_refs]


def test_rejects_processed_document_without_bundle():
    builder, _ = make_builder()

    with pytest.raises(InvalidCorpusSnapshotError, match="sin PersistenceBundle"):
        builder.build_snapshot(
            documents=[document("doc-surv", SourceType.SURVEILLANCE)],
            bundles=[],
        )


def test_references_are_complete_with_hash_and_version():
    builder, _ = make_builder()
    snapshot = builder.build_snapshot(
        documents=[document("doc-surv", SourceType.SURVEILLANCE)],
        bundles=[surveillance_bundle()],
    )

    for ref in snapshot.record_refs:
        assert ref.record_id
        assert ref.document_id == "doc-surv"
        assert ref.record_type
        assert ref.canonical_key
        assert len(ref.content_hash) == 64
        assert ref.record_version == NOW.isoformat()


def test_order_is_deterministic():
    builder, _ = make_builder()
    snapshot = builder.build_snapshot(
        documents=[
            document("doc-b", SourceType.SURVEILLANCE),
            document("doc-a", SourceType.SURVEILLANCE),
        ],
        bundles=[
            surveillance_bundle("doc-b"),
            surveillance_bundle("doc-a"),
        ],
    )

    assert snapshot.surveillance_document_ids == ("doc-a", "doc-b")
    assert [ref.sort_key() for ref in snapshot.record_refs] == sorted(
        ref.sort_key() for ref in snapshot.record_refs
    )
    assert sorted(ref.document_id for ref in snapshot.record_refs) == [
        "doc-a",
        "doc-a",
        "doc-a",
        "doc-b",
        "doc-b",
        "doc-b",
    ]


def test_hash_is_stable_for_same_content():
    builder_a, _ = make_builder()
    builder_b, _ = make_builder()
    docs = [document("doc-surv", SourceType.SURVEILLANCE)]
    bundles = [surveillance_bundle()]

    first = builder_a.build_snapshot(
        documents=docs,
        bundles=bundles,
        selection_criteria={"b": "2", "a": "1"},
    )
    second = builder_b.build_snapshot(
        documents=list(reversed(docs)),
        bundles=list(reversed(bundles)),
        selection_criteria={"a": "1", "b": "2"},
    )

    assert first.snapshot_hash == second.snapshot_hash


def test_hash_changes_when_content_or_criteria_change():
    builder_a, _ = make_builder()
    builder_b, _ = make_builder()
    builder_c, _ = make_builder()
    docs = [document("doc-surv", SourceType.SURVEILLANCE)]
    original = surveillance_bundle()
    changed = replace(
        original,
        findings=[
            record("finding-1", "doc-surv", data={"title": "contenido cambiado"})
        ],
    )

    first = builder_a.build_snapshot(documents=docs, bundles=[original])
    second = builder_b.build_snapshot(documents=docs, bundles=[changed])
    third = builder_c.build_snapshot(
        documents=docs,
        bundles=[original],
        selection_criteria={"until": "2026-07-13"},
    )

    assert first.snapshot_hash != second.snapshot_hash
    assert first.snapshot_hash != third.snapshot_hash


def test_rejects_empty_corpus_and_surveillance_without_findings():
    builder, _ = make_builder()

    with pytest.raises(InvalidCorpusSnapshotError, match="No hay documentos"):
        builder.build_snapshot(documents=[], bundles=[])

    with pytest.raises(InvalidCorpusSnapshotError, match="vigilancia"):
        builder.build_snapshot(
            documents=[document("doc-surv", SourceType.SURVEILLANCE)],
            bundles=[
                PersistenceBundle(
                    document_id="doc-surv",
                    document_analysis=record("analysis-1", "doc-surv"),
                    evidence=[record("evidence-1", "doc-surv")],
                )
            ],
        )


def test_repository_rejects_duplicate_snapshot_id_and_keeps_order():
    repo = InMemoryCorpusSnapshotRepository()
    builder, _ = make_builder(repo)
    first = builder.build_snapshot(
        documents=[document("doc-surv", SourceType.SURVEILLANCE)],
        bundles=[surveillance_bundle()],
    )

    with pytest.raises(DuplicateCorpusSnapshotError):
        repo.save_snapshot(first)

    second_builder = CorpusSnapshotBuilder(
        repo, uuid_factory=lambda: "snapshot-2", clock=lambda: NOW
    )
    second = second_builder.build_snapshot(
        documents=[document("doc-surv-2", SourceType.SURVEILLANCE)],
        bundles=[surveillance_bundle("doc-surv-2")],
    )

    assert repo.list_snapshots() == [first, second]


def test_saved_snapshot_is_immutable_from_external_mutation():
    builder, repo = make_builder()
    criteria = {"status": "processed"}
    snapshot = builder.build_snapshot(
        documents=[document("doc-surv", SourceType.SURVEILLANCE)],
        bundles=[surveillance_bundle()],
        selection_criteria=criteria,
    )

    criteria["status"] = "mutated"
    saved = repo.get_snapshot(snapshot.id)

    assert saved.selection_criteria["status"] == "processed"
    with pytest.raises(TypeError):
        saved.metadata["x"] = "y"


def test_rejects_incomplete_record_without_partial_save():
    builder, repo = make_builder()
    bad_bundle = PersistenceBundle(
        document_id="doc-surv",
        findings=[record("", "doc-surv")],
    )

    with pytest.raises(InvalidSnapshotReferenceError, match="id"):
        builder.build_snapshot(
            documents=[document("doc-surv", SourceType.SURVEILLANCE)],
            bundles=[bad_bundle],
        )

    assert repo.list_snapshots() == []


def test_builder_does_not_mutate_inputs():
    builder, _ = make_builder()
    docs = [document("doc-surv", SourceType.SURVEILLANCE)]
    bundles = [surveillance_bundle()]
    original_doc = docs[0]
    original_bundle = bundles[0]

    builder.build_snapshot(documents=docs, bundles=bundles)

    assert docs == [original_doc]
    assert bundles == [original_bundle]
