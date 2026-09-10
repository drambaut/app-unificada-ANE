from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.analysis_runs.models import (
    AnalysisRun,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageRun,
)
from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.in_memory_repository import InMemoryCorpusSnapshotRepository
from app.dashboard_read.errors import (
    IncompletePublishedRunError,
    InconsistentSnapshotError,
    NoPublishedAnalysisRunError,
)
from app.dashboard_read.service import DashboardReadService
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle, ResultRecord


NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeAnalysisRunRepository:
    def __init__(self, run: AnalysisRun | None, stages: list[AnalysisStageRun] | None = None):
        self.run = run
        self.stages = stages or []
        self.latest_calls = 0

    def get_latest_published_run(self):
        self.latest_calls += 1
        return self.run

    def list_stages(self, run_id: str):
        return [stage for stage in self.stages if stage.analysis_run_id == run_id]


class FakeSnapshotRepository:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot

    def get_snapshot(self, snapshot_id: str):
        if self.snapshot is not None and self.snapshot.id == snapshot_id:
            return self.snapshot
        return None


class FakeDocumentRepository:
    def __init__(self, documents: list[Document]):
        self.documents = {document.id: document for document in documents}
        self.requested_ids: list[str] = []

    def get_documents_by_ids(self, document_ids):
        self.requested_ids = list(document_ids)
        return [self.documents[document_id] for document_id in document_ids if document_id in self.documents]


class FakeResultRepository:
    def __init__(self, bundles: list[PersistenceBundle]):
        self.bundles = {bundle.document_id: bundle for bundle in bundles}
        self.requested_ids: list[str] = []

    def get_bundles_by_document_ids(self, document_ids):
        self.requested_ids = list(document_ids)
        return [self.bundles[document_id] for document_id in document_ids if document_id in self.bundles]


def test_no_published_run_raises():
    service = DashboardReadService(
        analysis_runs=FakeAnalysisRunRepository(None),
        snapshots=FakeSnapshotRepository(),
        documents=FakeDocumentRepository([]),
        results=FakeResultRepository([]),
    )

    with pytest.raises(NoPublishedAnalysisRunError):
        service.get_published_dashboard()


def test_incomplete_published_run_raises():
    fixture = _fixture()
    service = fixture.service(stages=fixture.stages[:-1])

    with pytest.raises(IncompletePublishedRunError):
        service.get_published_dashboard()


def test_missing_snapshot_raises():
    fixture = _fixture()
    service = DashboardReadService(
        analysis_runs=FakeAnalysisRunRepository(fixture.run, fixture.stages),
        snapshots=FakeSnapshotRepository(None),
        documents=FakeDocumentRepository(fixture.documents),
        results=FakeResultRepository(fixture.bundles),
    )

    with pytest.raises(InconsistentSnapshotError):
        service.get_published_dashboard()


def test_builds_full_dashboard_from_published_snapshot():
    fixture = _fixture()
    model = fixture.service().get_published_dashboard()

    assert model.summary.run_id == fixture.run.id
    assert model.summary.status == "published"
    assert model.summary.document_count == 3
    assert model.summary.finding_count == 1
    assert model.summary.evidence_count == 3
    assert model.summary.prompt_versions == {
        "thematic_landscape": "v1",
        "regulatory_intelligence": "v1",
        "strategic_assessment": "v1",
    }
    assert len(model.themes) == 1
    assert len(model.trends) == 1
    assert len(model.emerging_signals) == 1
    assert len(model.regulatory_intelligence) == 1
    assert len(model.gaps) == 2
    assert len(model.importance) == 1
    assert len(model.opportunities) == 1
    assert len(model.pmge_alignment) == 1
    assert len(model.documents) == 3
    assert {document.source_type for document in model.documents} == {
        "surveillance",
        "institutional_plan",
        "policy_matrix",
    }


def test_stable_public_ids_and_thematic_relations_are_preserved():
    fixture = _fixture()
    first = fixture.service().get_published_dashboard()
    second = fixture.service().get_published_dashboard()

    assert first.themes[0].id == second.themes[0].id
    assert first.trends[0].related_theme_ids == (first.themes[0].id,)
    assert first.emerging_signals[0].related_theme_ids == (first.themes[0].id,)
    assert first.regulatory_intelligence[0].theme_id == first.themes[0].id
    assert first.gaps[0].theme_id == first.themes[0].id


def test_scores_are_read_from_published_payload_without_recalculation():
    fixture = _fixture()
    model = fixture.service().get_published_dashboard()

    assert model.importance[0].importance_score == 12.34
    assert model.opportunities[0].opportunity_score == 56.78
    assert model.pmge_alignment[0].alignment_score == 90.12
    assert model.strategic_overview.average_importance_score == 12.34


def test_rejects_assessment_without_score():
    fixture = _fixture()
    strategic_payload = dict(fixture.strategic_payload)
    item = dict(strategic_payload["importance_assessments"][0])
    item.pop("importance_score")
    strategic_payload["importance_assessments"] = [item]
    stages = [
        stage
        if stage.stage != AnalysisStage.STRATEGIC_ASSESSMENT
        else replace(stage, result_payload=strategic_payload)
        for stage in fixture.stages
    ]

    with pytest.raises(Exception, match="importance_score"):
        fixture.service(stages=stages).get_published_dashboard()


def test_evidence_is_deduplicated_and_ordered():
    fixture = _fixture(duplicate_evidence=True)
    model = fixture.service().get_published_dashboard()

    assert tuple(item.id for item in model.evidence) == ("ev-1", "ev-plan", "ev-policy")


def test_records_missing_or_modified_are_rejected():
    fixture = _fixture()
    missing_finding = replace(fixture.surveillance_bundle, findings=[])
    service = fixture.service(bundles=[missing_finding, fixture.plan_bundle, fixture.policy_bundle])

    with pytest.raises(InconsistentSnapshotError, match="Records faltantes"):
        service.get_published_dashboard()

    changed_record = replace(
        fixture.finding,
        data={**fixture.finding.data, "title": "contenido cambiado"},
    )
    changed_bundle = replace(fixture.surveillance_bundle, findings=[changed_record])
    service = fixture.service(bundles=[changed_bundle, fixture.plan_bundle, fixture.policy_bundle])

    with pytest.raises(InconsistentSnapshotError, match="content_hash"):
        service.get_published_dashboard()


def test_records_outside_snapshot_are_rejected():
    fixture = _fixture()
    outsider = _record(
        "outside",
        "doc-surv",
        "finding|doc-surv|outside",
        {"title": "No congelado"},
    )
    bundle = replace(
        fixture.surveillance_bundle,
        findings=[*fixture.surveillance_bundle.findings, outsider],
    )

    with pytest.raises(InconsistentSnapshotError, match="Record ajeno"):
        fixture.service(bundles=[bundle, fixture.plan_bundle, fixture.policy_bundle]).get_published_dashboard()


def test_reads_only_documents_and_bundles_declared_by_snapshot():
    fixture = _fixture()
    document_repo = FakeDocumentRepository(fixture.documents + [_document("doc-extra", SourceType.SURVEILLANCE)])
    result_repo = FakeResultRepository(fixture.bundles + [PersistenceBundle(document_id="doc-extra")])
    service = DashboardReadService(
        analysis_runs=FakeAnalysisRunRepository(fixture.run, fixture.stages),
        snapshots=FakeSnapshotRepository(fixture.snapshot),
        documents=document_repo,
        results=result_repo,
    )

    model = service.get_published_dashboard()

    assert document_repo.requested_ids == ["doc-plan", "doc-policy", "doc-surv"]
    assert result_repo.requested_ids == ["doc-plan", "doc-policy", "doc-surv"]
    assert "doc-extra" not in {document.id for document in model.documents}


def test_does_not_expose_raw_payload_or_temporary_id_fields():
    fixture = _fixture()
    model = fixture.service().get_published_dashboard()

    assert not hasattr(model, "result_payload")
    for collection in (
        model.themes,
        model.trends,
        model.emerging_signals,
        model.regulatory_intelligence,
        model.importance,
        model.opportunities,
        model.pmge_alignment,
    ):
        for view in collection:
            assert not hasattr(view, "temporary_id")
            assert "temporary_id" not in view.__dataclass_fields__


def test_no_csv_or_gemini_dependencies_are_used(monkeypatch):
    fixture = _fixture()

    def fail_open(*args, **kwargs):
        raise AssertionError("No debe leer archivos CSV ni externos.")

    monkeypatch.setattr("builtins.open", fail_open)

    model = fixture.service().get_published_dashboard()

    assert model.summary.run_id == "run-1"


class _Fixture:
    pass


def _fixture(*, duplicate_evidence: bool = False):
    fixture = _Fixture()
    fixture.documents = [
        _document("doc-surv", SourceType.SURVEILLANCE),
        _document("doc-plan", SourceType.INSTITUTIONAL_PLAN),
        _document("doc-policy", SourceType.POLICY_MATRIX),
    ]
    fixture.finding = _record(
        "finding-1",
        "doc-surv",
        "finding|doc-surv|hallazgo|riesgo",
        {"title": "Hallazgo", "finding_type": "riesgo", "evidence_ids": ["ev-1"]},
    )
    evidence = _record(
        "ev-1",
        "doc-surv",
        "evidence|doc-surv|chunk-1|quote",
        {
            "quote": "Cita validada",
            "page_number": 1,
            "section_title": "Resumen",
            "matched_chunk_id": "chunk-1",
        },
    )
    fixture.surveillance_bundle = PersistenceBundle(
        document_id="doc-surv",
        document_analysis=_record(
            "analysis-1",
            "doc-surv",
            "document_analysis|doc-surv",
            {"title": "Documento de vigilancia"},
        ),
        findings=[fixture.finding],
        evidence=[evidence, evidence] if duplicate_evidence else [evidence],
    )
    fixture.plan_bundle = PersistenceBundle(
        document_id="doc-plan",
        pmge_projects=[
            _record("pmge-project-1", "doc-plan", "pmge_project|doc-plan|proyecto", {"project_name": "Proyecto"})
        ],
        pmge_objectives=[
            _record("pmge-objective-1", "doc-plan", "pmge_objective|doc-plan|objetivo", {"objective_text": "Objetivo"})
        ],
        pmge_activities=[
            _record("pmge-activity-1", "doc-plan", "pmge_activity|doc-plan|actividad", {"activity_name": "Actividad"})
        ],
        regulatory_agenda_initiatives=[
            _record(
                "agenda-1",
                "doc-plan",
                "agenda_initiative|doc-plan|iniciativa|2026",
                {"initiative_name": "Iniciativa", "period": "2026"},
            )
        ],
        regulatory_deliverables=[
            _record(
                "deliverable-1",
                "doc-plan",
                "agenda_deliverable|doc-plan|agenda-1|entregable",
                {"name": "Entregable"},
            )
        ],
        evidence=[
            _record(
                "ev-plan",
                "doc-plan",
                "evidence|doc-plan|chunk-plan|quote",
                {"quote": "Evidencia institucional", "page_number": 2, "matched_chunk_id": "chunk-plan"},
            )
        ],
    )
    fixture.policy_bundle = PersistenceBundle(
        document_id="doc-policy",
        policies=[
            _record("policy-1", "doc-policy", "policy|doc-policy|politica", {"policy_name": "Politica"})
        ],
        policy_activities=[
            _record(
                "policy-activity-1",
                "doc-policy",
                "policy_activity|doc-policy|policy-1|actividad",
                {"activity_name": "Actividad politica"},
            )
        ],
        policy_commitments=[
            _record(
                "policy-commitment-1",
                "doc-policy",
                "policy_commitment|doc-policy|policy-activity-1|compromiso",
                {"commitment_text": "Compromiso"},
            )
        ],
        evidence=[
            _record(
                "ev-policy",
                "doc-policy",
                "evidence|doc-policy|chunk-policy|quote",
                {
                    "quote": "Evidencia matriz",
                    "sheet_name": "Hoja 1",
                    "row_reference": "2",
                    "matched_chunk_id": "chunk-policy",
                },
            )
        ],
    )
    fixture.bundles = [
        fixture.surveillance_bundle,
        fixture.plan_bundle,
        fixture.policy_bundle,
    ]
    snapshot_repo = InMemoryCorpusSnapshotRepository()
    fixture.snapshot = CorpusSnapshotBuilder(
        snapshot_repo,
        uuid_factory=lambda: "snapshot-1",
        clock=lambda: NOW,
    ).build_snapshot(
        documents=fixture.documents,
        bundles=fixture.bundles,
        selection_criteria={"cutoff": "2026-01-01"},
    )
    fixture.run = AnalysisRun(
        id="run-1",
        corpus_snapshot_id=fixture.snapshot.id,
        status=AnalysisRunStatus.PUBLISHED,
        attempts=1,
        created_at=NOW,
        updated_at=NOW,
        started_at=NOW,
        completed_at=NOW,
        published_at=NOW,
        failed_at=None,
        error_message=None,
    )
    fixture.thematic_payload = _thematic_payload()
    fixture.regulatory_payload = _regulatory_payload()
    fixture.strategic_payload = _strategic_payload()
    fixture.stages = [
        _stage(
            "stage-theme",
            AnalysisStage.THEMATIC_LANDSCAPE,
            "thematic_landscape",
            "ThematicLandscape",
            fixture.thematic_payload,
        ),
        _stage(
            "stage-reg",
            AnalysisStage.REGULATORY_INTELLIGENCE,
            "regulatory_intelligence",
            "RegulatoryIntelligence",
            fixture.regulatory_payload,
        ),
        _stage(
            "stage-strategic",
            AnalysisStage.STRATEGIC_ASSESSMENT,
            "strategic_assessment",
            "StrategicAssessment",
            fixture.strategic_payload,
        ),
    ]

    def service(*, stages=None, bundles=None):
        return DashboardReadService(
            analysis_runs=FakeAnalysisRunRepository(fixture.run, stages or fixture.stages),
            snapshots=FakeSnapshotRepository(fixture.snapshot),
            documents=FakeDocumentRepository(fixture.documents),
            results=FakeResultRepository(bundles or fixture.bundles),
        )

    fixture.service = service
    return fixture


def _document(document_id: str, source_type: SourceType) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type="pdf",
        source_type=source_type,
        file_hash=f"hash-{document_id}",
        storage_path=None,
        document_date=None,
        status=DocumentStatus.PROCESSED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _record(record_id: str, document_id: str, canonical_key: str, data: dict) -> ResultRecord:
    return ResultRecord(
        id=record_id,
        document_id=document_id,
        data=data,
        prompt_id="prompt",
        prompt_version="v1",
        contract_name="Contract",
        model_name="fake-model",
        created_at=NOW,
        canonical_key=canonical_key,
        confidence=data.get("confidence"),
        extraction_basis=data.get("extraction_basis"),
    )


def _stage(
    stage_id: str,
    stage: AnalysisStage,
    prompt_id: str,
    contract_name: str,
    payload: dict,
) -> AnalysisStageRun:
    return AnalysisStageRun(
        id=stage_id,
        analysis_run_id="run-1",
        stage=stage,
        status=AnalysisRunStatus.COMPLETED,
        prompt_id=prompt_id,
        prompt_version="v1",
        contract_name=contract_name,
        attempts=1,
        created_at=NOW,
        updated_at=NOW,
        started_at=NOW,
        completed_at=NOW,
        failed_at=None,
        error_message=None,
        result_payload=payload,
    )


def _thematic_payload() -> dict:
    return {
        "corpus_summary": "Resumen publicado",
        "themes": [
            {
                "temporary_id": "theme-1",
                "name": "Tema abierto",
                "definition": "Definicion",
                "scope": "Alcance",
                "subthemes": ["subtema"],
                "technologies": ["5G"],
                "frequency_bands": ["6 GHz"],
                "countries_regions": ["Colombia"],
                "organizations": ["ANE"],
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "change_action": "create",
                "confidence": "Alta",
                "extraction_basis": "mixed",
            }
        ],
        "trends": [
            {
                "temporary_id": "trend-1",
                "name": "Tendencia",
                "description": "Crecimiento sostenido",
                "related_theme_temporary_ids": ["theme-1"],
                "direction": "growing",
                "time_horizon": "short_term",
                "countries_regions": ["Colombia"],
                "organizations": ["ANE"],
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
            }
        ],
        "emerging_signals": [
            {
                "temporary_id": "signal-1",
                "title": "Senal",
                "description": "Senal minoritaria",
                "novelty_explanation": "Aparece en evidencia reciente",
                "related_theme_temporary_ids": ["theme-1"],
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "confidence": "Media",
            }
        ],
    }


def _regulatory_payload() -> dict:
    return {
        "analyses": [
            {
                "temporary_id": "reg-1",
                "theme_temporary_id": "theme-1",
                "international_situation": "Situacion internacional",
                "regulatory_debate": "Debate regulatorio",
                "countries_regions": ["Colombia"],
                "organizations": ["ANE"],
                "agenda_item_ids": ["agenda-1"],
                "relationship_type": "gap",
                "coverage_explanation": "Brecha identificada",
                "implications_for_ane": "Implicacion",
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
                "extraction_basis": "explicit",
            }
        ],
        "overall_gaps": ["Brecha agregada"],
        "evidence_ids": ["ev-1"],
    }


def _strategic_payload() -> dict:
    return {
        "importance_assessments": [
            {
                "temporary_id": "importance-1",
                "subject_type": "theme",
                "subject_id": "theme-1",
                "dimensions": {
                    "ane_relevance": 1,
                    "magnitude": 2,
                    "urgency": 3,
                    "evidence_strength": 4,
                    "institutional_scope": 5,
                },
                "importance_score": 12.34,
                "level": "media",
                "rationale": "Razon",
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
            }
        ],
        "opportunity_assessments": [
            {
                "temporary_id": "opportunity-1",
                "theme_id": "theme-1",
                "policy_activity_ids": ["policy-activity-1"],
                "dimensions": {
                    "policy_gap": 1,
                    "institutional_relevance": 2,
                    "actionability": 3,
                    "evidence_maturity": 4,
                    "timing": 5,
                },
                "opportunity_score": 56.78,
                "level": "alta",
                "rationale": "Oportunidad",
                "suggested_action": "Explorar accion",
                "evidence_ids": ["ev-policy"],
                "confidence": "Media",
            }
        ],
        "alignment_assessments": [
            {
                "temporary_id": "alignment-1",
                "theme_id": "theme-1",
                "pmge_project_ids": ["pmge-project-1"],
                "dimensions": {
                    "objective_match": 1,
                    "activity_match": 2,
                    "deliverable_match": 3,
                    "temporal_match": 4,
                    "evidence_strength": 5,
                },
                "alignment_score": 90.12,
                "level": "alta",
                "rationale": "Alineacion",
                "alignment_type": "directa",
                "evidence_ids": ["ev-plan"],
                "confidence": "Alta",
            }
        ],
    }
