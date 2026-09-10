"""Pruebas de contratos de lectura para dashboard publicado."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, date, datetime

import pytest

from app.dashboard_read.errors import (
    DashboardMappingError,
    DashboardReadError,
    IncompletePublishedRunError,
    InconsistentSnapshotError,
    NoPublishedAnalysisRunError,
)
from app.dashboard_read.models import (
    DashboardReadModel,
    EmergingSignalView,
    EvidenceView,
    GapView,
    ImportanceView,
    OpportunityView,
    PmgeAlignmentView,
    ProcessedDocumentView,
    PublishedRunSummary,
    RegulatoryIntelligenceView,
    StrategicOverview,
    ThemeView,
    TrendView,
)
from app.dashboard_read.repository import (
    DashboardDocumentReadRepository,
    DashboardResultReadRepository,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def summary() -> PublishedRunSummary:
    return PublishedRunSummary(
        run_id="run-1",
        snapshot_id="snapshot-1",
        status="published",
        created_at=NOW,
        completed_at=NOW,
        published_at=NOW,
        prompt_versions={"strategic_assessment": "v1", "thematic_landscape": "v1"},
        document_count=2,
        finding_count=3,
        evidence_count=4,
    )


def theme(theme_id: str = "theme-1") -> ThemeView:
    return ThemeView(
        id=theme_id,
        name="Tema",
        definition="Definicion",
        scope="Alcance",
        subthemes=("b", "a"),
        technologies=("5G",),
        frequency_bands=("6 GHz",),
        countries_regions=("Colombia",),
        organizations=("ANE",),
        finding_ids=("finding-2", "finding-1"),
        evidence_ids=("ev-2", "ev-1"),
        change_action="create",
        confidence="Alta",
        extraction_basis="mixed",
    )


def trend() -> TrendView:
    return TrendView(
        id="trend-1",
        name="Tendencia",
        description="Descripcion",
        related_theme_ids=("theme-1",),
        direction="growing",
        time_horizon="short_term",
        countries_regions=("Colombia",),
        organizations=("ANE",),
        finding_ids=("finding-1",),
        evidence_ids=("ev-1",),
        confidence="Alta",
    )


def signal() -> EmergingSignalView:
    return EmergingSignalView(
        id="signal-1",
        title="Senal",
        description="Descripcion",
        novelty_explanation="Novedad",
        related_theme_ids=("theme-1",),
        finding_ids=("finding-1",),
        evidence_ids=("ev-1",),
        confidence="Media",
    )


def regulatory() -> RegulatoryIntelligenceView:
    return RegulatoryIntelligenceView(
        id="reg-1",
        theme_id="theme-1",
        international_situation="Situacion",
        regulatory_debate="Debate",
        countries_regions=("Colombia",),
        organizations=("ANE",),
        agenda_item_ids=("agenda-1",),
        relationship_type="gap",
        coverage_explanation="Brecha",
        implications_for_ane="Implicaciones",
        finding_ids=("finding-1",),
        evidence_ids=("ev-1",),
        confidence="Alta",
        extraction_basis="explicit",
    )


def dashboard_model() -> DashboardReadModel:
    return DashboardReadModel(
        summary=summary(),
        strategic_overview=StrategicOverview(
            theme_count=1,
            trend_count=1,
            emerging_signal_count=1,
            regulatory_analysis_count=1,
            gap_count=1,
            importance_count=1,
            opportunity_count=1,
            pmge_alignment_count=1,
            average_importance_score=84.0,
            average_opportunity_score=50.0,
            average_alignment_score=0.0,
        ),
        themes=(theme("theme-b"), theme("theme-a")),
        trends=(trend(),),
        emerging_signals=(signal(),),
        regulatory_intelligence=(regulatory(),),
        gaps=(
            GapView(
                id="gap-1",
                relationship_type="gap",
                description="Brecha",
                theme_id="theme-1",
                agenda_item_ids=("agenda-1",),
                finding_ids=("finding-1",),
                evidence_ids=("ev-1",),
            ),
        ),
        importance=(
            ImportanceView(
                id="importance-1",
                subject_type="theme",
                subject_id="theme-1",
                dimensions={"urgency": 3, "ane_relevance": 5},
                importance_score=84.0,
                level="Alta",
                rationale="Razon",
                evidence_ids=("ev-1",),
                confidence="Alta",
            ),
        ),
        opportunities=(
            OpportunityView(
                id="opportunity-1",
                theme_id="theme-1",
                policy_activity_ids=("policy-1",),
                dimensions={"timing": 2.5},
                opportunity_score=50.0,
                level="Media",
                rationale="Razon",
                suggested_action="Accion",
                evidence_ids=("ev-1",),
                confidence="Alta",
            ),
        ),
        pmge_alignment=(
            PmgeAlignmentView(
                id="alignment-1",
                theme_id="theme-1",
                pmge_project_ids=("project-1",),
                dimensions={"objective_match": 0},
                alignment_score=0.0,
                level="Baja",
                rationale="Razon",
                alignment_type="weak",
                evidence_ids=("ev-1",),
                confidence="Alta",
            ),
        ),
        evidence=(
            EvidenceView(
                id="ev-1",
                document_id="doc-1",
                quote="cita",
                page_number=1,
                section_title=None,
                sheet_name=None,
                row_reference=None,
                matched_chunk_id="chunk-1",
            ),
        ),
        documents=(
            ProcessedDocumentView(
                id="doc-1",
                file_name="doc.pdf",
                file_type=".pdf",
                source_type="surveillance",
                document_date=date(2026, 1, 1),
                status="processed",
            ),
        ),
    )


def test_models_are_frozen():
    model = dashboard_model()

    with pytest.raises(FrozenInstanceError):
        model.summary = summary()
    with pytest.raises(FrozenInstanceError):
        model.themes[0].name = "Otro"


def test_mappings_are_deeply_immutable_and_defensive():
    versions = {"b": "v2", "a": "v1"}
    dims = {"z": 1, "a": 2}
    run = summary()
    importance = ImportanceView(
        id="importance-1",
        subject_type="theme",
        subject_id="theme-1",
        dimensions=dims,
        importance_score=40.0,
        level="Media",
        rationale="Razon",
        evidence_ids=("ev-1",),
        confidence="Alta",
    )
    copied = PublishedRunSummary(
        run_id=run.run_id,
        snapshot_id=run.snapshot_id,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        published_at=run.published_at,
        prompt_versions=versions,
        document_count=run.document_count,
        finding_count=run.finding_count,
        evidence_count=run.evidence_count,
    )

    versions["a"] = "mutated"
    dims["a"] = 99

    assert tuple(copied.prompt_versions.keys()) == ("a", "b")
    assert copied.prompt_versions["a"] == "v1"
    assert importance.dimensions["a"] == 2
    with pytest.raises(TypeError):
        copied.prompt_versions["a"] = "v3"
    with pytest.raises(TypeError):
        importance.dimensions["a"] = 3


def test_collections_are_sorted_deterministically():
    model = dashboard_model()

    assert [item.id for item in model.themes] == ["theme-a", "theme-b"]
    assert model.themes[0].finding_ids == ("finding-1", "finding-2")
    assert model.themes[0].evidence_ids == ("ev-1", "ev-2")


def test_no_internal_or_legacy_fields_are_exposed():
    all_field_names = {
        field.name
        for cls in (
            PublishedRunSummary,
            ThemeView,
            TrendView,
            EmergingSignalView,
            RegulatoryIntelligenceView,
            ImportanceView,
            OpportunityView,
            PmgeAlignmentView,
            ProcessedDocumentView,
            DashboardReadModel,
        )
        for field in fields(cls)
    }

    assert "result_payload" not in all_field_names
    assert "temporary_id" not in all_field_names
    assert "theme_temporary_id" not in all_field_names
    assert "model_names" not in all_field_names
    assert "version" not in {field.name for field in fields(ProcessedDocumentView)}


def test_traceability_ids_and_scores_are_preserved():
    model = dashboard_model()

    assert model.themes[0].finding_ids == ("finding-1", "finding-2")
    assert model.regulatory_intelligence[0].agenda_item_ids == ("agenda-1",)
    assert model.opportunities[0].policy_activity_ids == ("policy-1",)
    assert model.pmge_alignment[0].pmge_project_ids == ("project-1",)
    assert model.importance[0].importance_score == 84.0
    assert model.opportunities[0].opportunity_score == 50.0
    assert model.pmge_alignment[0].alignment_score == 0.0


def test_protocols_are_structurally_compatible():
    class DocumentReader:
        def get_documents_by_ids(self, document_ids):
            return []

    class ResultReader:
        def get_bundles_by_document_ids(self, document_ids):
            return []

    document_reader: DashboardDocumentReadRepository = DocumentReader()
    result_reader: DashboardResultReadRepository = ResultReader()

    assert document_reader.get_documents_by_ids(["doc-1"]) == []
    assert result_reader.get_bundles_by_document_ids(["doc-1"]) == []


def test_custom_errors_share_base_type():
    for error_type in (
        NoPublishedAnalysisRunError,
        IncompletePublishedRunError,
        InconsistentSnapshotError,
        DashboardMappingError,
    ):
        assert issubclass(error_type, DashboardReadError)


def test_minimal_dashboard_read_model_construction():
    model = DashboardReadModel(
        summary=summary(),
        strategic_overview=StrategicOverview(
            theme_count=0,
            trend_count=0,
            emerging_signal_count=0,
            regulatory_analysis_count=0,
            gap_count=0,
            importance_count=0,
            opportunity_count=0,
            pmge_alignment_count=0,
        ),
        themes=(),
        trends=(),
        emerging_signals=(),
        regulatory_intelligence=(),
        gaps=(),
        importance=(),
        opportunities=(),
        pmge_alignment=(),
        evidence=(),
        documents=(),
    )

    assert model.summary.run_id == "run-1"
    assert model.themes == ()
