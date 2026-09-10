"""Pruebas de construccion de contextos transversales."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.context_builder import CorpusContextBuilder
from app.corpus_snapshots.errors import InvalidCorpusSnapshotError
from app.corpus_snapshots.in_memory_repository import InMemoryCorpusSnapshotRepository
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle, ResultRecord


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def document(document_id: str, source_type: SourceType) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type=".pdf",
        source_type=source_type,
        file_hash=f"file-hash-{document_id}",
        storage_path=f"storage/{document_id}.pdf",
        document_date=date(2026, 1, 1),
        status=DocumentStatus.PROCESSED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def record(
    record_type: str,
    record_id: str,
    document_id: str,
    *,
    data: dict | None = None,
    created_at: datetime = NOW,
) -> ResultRecord:
    return ResultRecord(
        id=record_id,
        document_id=document_id,
        data=data or {"name": record_id},
        prompt_id="source_prompt",
        prompt_version="v1",
        contract_name="SourceContract",
        model_name="fake",
        created_at=created_at,
        canonical_key=f"{record_type}|{document_id}|{record_id}",
        confidence="Alta",
        extraction_basis="explicit",
    )


def surveillance_bundle() -> PersistenceBundle:
    return PersistenceBundle(
        document_id="doc-surv",
        document_analysis=record(
            "document_analysis",
            "analysis-1",
            "doc-surv",
            data={"title": "Documento vigilancia", "evidence_ids": ["ev-1"]},
        ),
        findings=[
            record(
                "finding",
                "finding-1",
                "doc-surv",
                data={
                    "title": "Riesgo",
                    "description": "Hallazgo",
                    "evidence_ids": ["ev-1"],
                },
            ),
            record(
                "finding",
                "finding-2",
                "doc-surv",
                data={
                    "title": "Oportunidad",
                    "description": "Hallazgo",
                    "evidence_ids": ["ev-1"],
                },
            ),
        ],
        evidence=[
            record(
                "evidence",
                "ev-1",
                "doc-surv",
                data={"quote": "cita vigilancia", "page_number": 1},
            )
        ],
    )


def institutional_bundle() -> PersistenceBundle:
    return PersistenceBundle(
        document_id="doc-plan",
        pmge_projects=[
            record(
                "pmge_project",
                "pmge-project-1",
                "doc-plan",
                data={"project_name": "Proyecto", "evidence_ids": ["ev-plan"]},
            )
        ],
        pmge_objectives=[
            record(
                "pmge_objective",
                "pmge-objective-1",
                "doc-plan",
                data={"objective_text": "Objetivo", "evidence_ids": ["ev-plan"]},
            )
        ],
        pmge_activities=[
            record(
                "pmge_activity",
                "pmge-activity-1",
                "doc-plan",
                data={"activity_name": "Actividad", "evidence_ids": ["ev-plan"]},
            )
        ],
        regulatory_agenda_initiatives=[
            record(
                "agenda_initiative",
                "agenda-1",
                "doc-plan",
                data={"initiative_name": "Agenda", "evidence_ids": ["ev-plan"]},
            )
        ],
        regulatory_deliverables=[
            record(
                "agenda_deliverable",
                "deliverable-1",
                "doc-plan",
                data={"name": "Entregable", "evidence_ids": ["ev-plan"]},
            )
        ],
        evidence=[
            record(
                "evidence",
                "ev-plan",
                "doc-plan",
                data={"quote": "cita institucional", "page_number": 2},
            )
        ],
    )


def policy_bundle() -> PersistenceBundle:
    return PersistenceBundle(
        document_id="doc-policy",
        policies=[
            record(
                "policy",
                "policy-1",
                "doc-policy",
                data={"policy_name": "Politica", "evidence_ids": ["ev-policy"]},
            )
        ],
        policy_activities=[
            record(
                "policy_activity",
                "policy-activity-1",
                "doc-policy",
                data={"activity_name": "Actividad", "evidence_ids": ["ev-policy"]},
            )
        ],
        policy_commitments=[
            record(
                "policy_commitment",
                "commitment-1",
                "doc-policy",
                data={"commitment_text": "Compromiso", "evidence_ids": ["ev-policy"]},
            )
        ],
        evidence=[
            record(
                "evidence",
                "ev-policy",
                "doc-policy",
                data={"quote": "cita matriz", "sheet_name": "Matriz"},
            )
        ],
    )


def build_fixture():
    docs = [
        document("doc-surv", SourceType.SURVEILLANCE),
        document("doc-plan", SourceType.INSTITUTIONAL_PLAN),
        document("doc-policy", SourceType.POLICY_MATRIX),
    ]
    bundles = [surveillance_bundle(), institutional_bundle(), policy_bundle()]
    builder = CorpusSnapshotBuilder(
        InMemoryCorpusSnapshotRepository(),
        uuid_factory=lambda: "snapshot-1",
        clock=lambda: NOW,
    )
    snapshot = builder.build_snapshot(documents=docs, bundles=bundles)
    return snapshot, docs, bundles


def thematic_result() -> dict:
    return {
        "themes": [
            {
                "temporary_id": "theme-1",
                "name": "Tema",
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
            }
        ],
        "trends": [],
        "emerging_signals": [],
    }


def test_thematic_context_only_includes_surveillance_data():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )

    assert context.snapshot_id == snapshot.id
    assert [item["id"] for item in context.payload["document_analysis"]] == [
        "analysis-1"
    ]
    assert [item["id"] for item in context.payload["findings"]] == [
        "finding-1",
        "finding-2",
    ]
    assert [item["id"] for item in context.payload["evidence"]] == ["ev-1"]
    assert "pmge_projects" not in context.payload
    assert "agenda_regulatoria" not in context.payload
    assert "policy_activities" not in context.payload


def test_regulatory_context_excludes_pmge_and_policy_matrix():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_regulatory_intelligence_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        thematic_result=thematic_result(),
        prompt_id="regulatory_intelligence",
        prompt_version="v1",
    )

    assert context.payload["thematic_landscape"]["themes"][0]["name"] == "Tema"
    assert [item["id"] for item in context.payload["surveillance"]["findings"]] == [
        "finding-1",
        "finding-2",
    ]
    assert [item["id"] for item in context.payload["agenda_regulatoria"]["initiatives"]] == [
        "agenda-1"
    ]
    assert "pmge_projects" not in str(context.payload)
    assert "policy_activity" not in str(context.payload)


def test_strategic_context_separates_importance_opportunity_and_alignment():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_strategic_assessment_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        thematic_result=thematic_result(),
        prompt_id="strategic_assessment",
        prompt_version="v1",
    )

    assert [item["id"] for item in context.payload["importance_inputs"]["findings"]] == [
        "finding-1",
        "finding-2",
    ]
    assert [
        item["id"]
        for item in context.payload["opportunity_inputs"]["policy_activities"]
    ] == ["policy-activity-1"]
    assert [
        item["id"] for item in context.payload["alignment_inputs"]["pmge_projects"]
    ] == ["pmge-project-1"]
    assert "agenda-1" not in str(context.payload)


def test_rejects_missing_modified_or_version_changed_records():
    snapshot, docs, bundles = build_fixture()
    context_builder = CorpusContextBuilder()

    missing_bundle = replace(bundles[0], findings=bundles[0].findings[:1])
    with pytest.raises(InvalidCorpusSnapshotError, match="Records faltantes"):
        context_builder.build_thematic_landscape_context(
            snapshot=snapshot,
            documents=docs,
            bundles=[missing_bundle, *bundles[1:]],
            prompt_id="thematic_landscape",
            prompt_version="v1",
        )

    modified_record = replace(
        bundles[0].findings[0],
        data={"title": "mutado", "evidence_ids": ["ev-1"]},
    )
    modified_bundle = replace(
        bundles[0], findings=[modified_record, bundles[0].findings[1]]
    )
    with pytest.raises(InvalidCorpusSnapshotError, match="content_hash"):
        context_builder.build_thematic_landscape_context(
            snapshot=snapshot,
            documents=docs,
            bundles=[modified_bundle, *bundles[1:]],
            prompt_id="thematic_landscape",
            prompt_version="v1",
        )

    version_record = replace(
        bundles[0].findings[0],
        created_at=NOW + timedelta(days=1),
    )
    version_bundle = replace(
        bundles[0], findings=[version_record, bundles[0].findings[1]]
    )
    with pytest.raises(InvalidCorpusSnapshotError, match="record_version"):
        context_builder.build_thematic_landscape_context(
            snapshot=snapshot,
            documents=docs,
            bundles=[version_bundle, *bundles[1:]],
            prompt_id="thematic_landscape",
            prompt_version="v1",
        )


def test_rejects_records_not_frozen_in_snapshot():
    snapshot, docs, bundles = build_fixture()
    extra_bundle = replace(
        bundles[0],
        findings=[
            *bundles[0].findings,
            record("finding", "finding-extra", "doc-surv", data={"evidence_ids": []}),
        ],
    )

    with pytest.raises(InvalidCorpusSnapshotError, match="ajeno"):
        CorpusContextBuilder().build_thematic_landscape_context(
            snapshot=snapshot,
            documents=docs,
            bundles=[extra_bundle, *bundles[1:]],
            prompt_id="thematic_landscape",
            prompt_version="v1",
        )


def test_deduplicates_evidence_and_included_ids_are_sorted():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )

    assert [item["id"] for item in context.payload["evidence"]] == ["ev-1"]
    assert context.included_ids == tuple(sorted(context.included_ids))
    assert context.included_ids == (
        "analysis-1",
        "doc-surv",
        "ev-1",
        "finding-1",
        "finding-2",
    )


def test_context_hash_is_deterministic_and_changes_with_payload():
    snapshot, docs, bundles = build_fixture()
    builder = CorpusContextBuilder()

    first = builder.build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )
    second = builder.build_thematic_landscape_context(
        snapshot=snapshot,
        documents=list(reversed(docs)),
        bundles=list(reversed(bundles)),
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )
    limited = CorpusContextBuilder(max_records_by_type={"findings": 1})
    third = limited.build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )

    assert first.context_hash == second.context_hash
    assert first.context_hash != third.context_hash
    assert third.omitted_counts["findings"] == 1


def test_payload_is_immutable_and_omitted_counts_exists():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )

    assert dict(context.omitted_counts) == {}
    with pytest.raises(TypeError):
        context.payload["findings"][0]["id"] = "mutado"


def test_thematic_result_is_required_for_dependent_contexts():
    snapshot, docs, bundles = build_fixture()

    with pytest.raises(InvalidCorpusSnapshotError, match="thematic_result"):
        CorpusContextBuilder().build_regulatory_intelligence_context(
            snapshot=snapshot,
            documents=docs,
            bundles=bundles,
            thematic_result=None,
            prompt_id="regulatory_intelligence",
            prompt_version="v1",
        )
    with pytest.raises(InvalidCorpusSnapshotError, match="thematic_result"):
        CorpusContextBuilder().build_strategic_assessment_context(
            snapshot=snapshot,
            documents=docs,
            bundles=bundles,
            thematic_result=None,
            prompt_id="strategic_assessment",
            prompt_version="v1",
        )


def test_contexts_do_not_include_full_documents_or_chunks():
    snapshot, docs, bundles = build_fixture()
    context = CorpusContextBuilder().build_thematic_landscape_context(
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        prompt_id="thematic_landscape",
        prompt_version="v1",
    )

    serialized = str(context.payload)
    assert "file_hash" not in serialized
    assert "storage_path" not in serialized
    assert "chunks" not in serialized
    assert "content_hash" not in serialized


def test_rejects_empty_context_and_invalid_limit():
    snapshot, docs, bundles = build_fixture()
    no_surveillance_snapshot = replace(
        snapshot,
        surveillance_document_ids=(),
        record_refs=tuple(
            ref for ref in snapshot.record_refs if ref.document_id != "doc-surv"
        ),
    )

    with pytest.raises(InvalidCorpusSnapshotError, match="contexto"):
        CorpusContextBuilder().build_thematic_landscape_context(
            snapshot=no_surveillance_snapshot,
            documents=docs,
            bundles=bundles,
            prompt_id="thematic_landscape",
            prompt_version="v1",
        )

    with pytest.raises(InvalidCorpusSnapshotError, match="Limite invalido"):
        CorpusContextBuilder(max_records_by_type={"findings": 0})
