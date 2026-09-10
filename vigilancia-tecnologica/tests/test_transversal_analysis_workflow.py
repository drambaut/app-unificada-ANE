"""Pruebas del workflow integral de analisis transversal."""

from __future__ import annotations

import json
import copy
from datetime import UTC, date, datetime

import pytest

from app.analysis_runs.errors import ConcurrentAnalysisRunError
from app.analysis_runs.in_memory_repository import InMemoryAnalysisRunRepository
from app.analysis_runs.models import AnalysisRunStatus, AnalysisStage
from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.context_builder import CorpusContextBuilder
from app.corpus_snapshots.in_memory_repository import InMemoryCorpusSnapshotRepository
from app.documents.models import Document, DocumentStatus, SourceType
from app.llm.base import LLMInput
from app.llm.errors import InvalidLLMJSONError
from app.llm.service import StructuredExtractionService
from app.results.models import PersistenceBundle, ResultRecord
from app.workflows.transversal_analysis import (
    TransversalAnalysisWorkflow,
    TransversalAnalysisWorkflowError,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeTransversalClient:
    model_name = "fake-transversal-model"

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[dict] = []

    def generate_json(
        self, *, prompt: str, input_data: LLMInput, response_schema: dict
    ) -> dict:
        contract = response_schema["title"]
        self.calls.append(
            {
                "contract": contract,
                "input_data": input_data,
                "text": input_data.text,
                "prompt": prompt,
            }
        )
        if self.fail_on == contract:
            raise RuntimeError(f"fallo {contract}")
        return {
            "ThematicLandscape": thematic_payload(),
            "RegulatoryIntelligence": regulatory_payload(),
            "StrategicAssessment": strategic_payload(),
        }[contract]


class SpyScorer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def __call__(self, payload: dict) -> dict:
        self.calls.append(copy.deepcopy(payload))
        if self.fail:
            raise RuntimeError("fallo scoring")
        scored = copy.deepcopy(payload)
        for item in scored["importance_assessments"]:
            item["importance_score"] = 84.0
        for item in scored["opportunity_assessments"]:
            item["opportunity_score"] = 50.0
        for item in scored["alignment_assessments"]:
            item["alignment_score"] = 0.0
        return scored


def document(document_id: str, source_type: SourceType) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type=".pdf",
        source_type=source_type,
        file_hash=f"hash-{document_id}",
        storage_path=f"storage/{document_id}.pdf",
        document_date=date(2026, 1, 1),
        status=DocumentStatus.PROCESSED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def record(record_type: str, record_id: str, document_id: str, data: dict) -> ResultRecord:
    return ResultRecord(
        id=record_id,
        document_id=document_id,
        data=data,
        prompt_id="source_prompt",
        prompt_version="v1",
        contract_name="SourceContract",
        model_name="fake",
        created_at=NOW,
        canonical_key=f"{record_type}|{document_id}|{record_id}",
        confidence="Alta",
        extraction_basis="explicit",
    )


def fixtures():
    docs = [
        document("doc-surv", SourceType.SURVEILLANCE),
        document("doc-plan", SourceType.INSTITUTIONAL_PLAN),
        document("doc-policy", SourceType.POLICY_MATRIX),
    ]
    bundles = [
        PersistenceBundle(
            document_id="doc-surv",
            document_analysis=record(
                "document_analysis",
                "analysis-1",
                "doc-surv",
                {"title": "Documento", "evidence_ids": ["ev-1"]},
            ),
            findings=[
                record(
                    "finding",
                    "finding-1",
                    "doc-surv",
                    {"title": "Hallazgo", "evidence_ids": ["ev-1"]},
                )
            ],
            evidence=[
                record("evidence", "ev-1", "doc-surv", {"quote": "cita"})
            ],
        ),
        PersistenceBundle(
            document_id="doc-plan",
            pmge_projects=[
                record(
                    "pmge_project",
                    "pmge-project-1",
                    "doc-plan",
                    {"project_name": "Proyecto", "evidence_ids": ["ev-plan"]},
                )
            ],
            pmge_objectives=[
                record(
                    "pmge_objective",
                    "objective-1",
                    "doc-plan",
                    {"objective_text": "Objetivo", "evidence_ids": ["ev-plan"]},
                )
            ],
            pmge_activities=[
                record(
                    "pmge_activity",
                    "activity-1",
                    "doc-plan",
                    {"activity_name": "Actividad", "evidence_ids": ["ev-plan"]},
                )
            ],
            regulatory_agenda_initiatives=[
                record(
                    "agenda_initiative",
                    "agenda-1",
                    "doc-plan",
                    {"initiative_name": "Agenda", "evidence_ids": ["ev-plan"]},
                )
            ],
            regulatory_deliverables=[
                record(
                    "agenda_deliverable",
                    "deliverable-1",
                    "doc-plan",
                    {"name": "Entregable", "evidence_ids": ["ev-plan"]},
                )
            ],
            evidence=[
                record("evidence", "ev-plan", "doc-plan", {"quote": "plan"})
            ],
        ),
        PersistenceBundle(
            document_id="doc-policy",
            policies=[
                record(
                    "policy",
                    "policy-1",
                    "doc-policy",
                    {"policy_name": "Politica", "evidence_ids": ["ev-policy"]},
                )
            ],
            policy_activities=[
                record(
                    "policy_activity",
                    "policy-activity-1",
                    "doc-policy",
                    {"activity_name": "Actividad", "evidence_ids": ["ev-policy"]},
                )
            ],
            policy_commitments=[
                record(
                    "policy_commitment",
                    "commitment-1",
                    "doc-policy",
                    {"commitment_text": "Compromiso", "evidence_ids": ["ev-policy"]},
                )
            ],
            evidence=[
                record("evidence", "ev-policy", "doc-policy", {"quote": "matriz"})
            ],
        ),
    ]
    return docs, bundles


def thematic_payload() -> dict:
    return {
        "corpus_summary": "Resumen.",
        "themes": [
            {
                "temporary_id": "theme-1",
                "name": "Tema",
                "definition": "Definicion",
                "scope": "Alcance",
                "subthemes": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "change_action": "create",
                "previous_topic_ids": [],
                "confidence": "Alta",
                "extraction_basis": "mixed",
            }
        ],
        "trends": [],
        "emerging_signals": [],
        "evidence_ids": ["ev-1"],
    }


def regulatory_payload() -> dict:
    return {
        "analyses": [
            {
                "temporary_id": "reg-1",
                "theme_temporary_id": "theme-1",
                "international_situation": "Situacion",
                "regulatory_debate": "Debate",
                "countries_regions": [],
                "organizations": [],
                "agenda_item_ids": ["agenda-1"],
                "relationship_type": "covered",
                "coverage_explanation": "Cubierto",
                "implications_for_ane": "Implicaciones",
                "finding_ids": ["finding-1"],
                "evidence_ids": ["ev-1"],
                "confidence": "Alta",
                "extraction_basis": "explicit",
            }
        ],
        "overall_gaps": [],
        "evidence_ids": ["ev-1"],
    }


def strategic_payload() -> dict:
    return {
        "importance_assessments": [
            {
                "temporary_id": "importance-1",
                "subject_type": "theme",
                "subject_id": "theme-1",
                "dimensions": {
                    "ane_relevance": 5,
                    "magnitude": 4,
                    "urgency": 3,
                    "evidence_strength": 4,
                    "institutional_scope": 5,
                },
                "level": "Alta",
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
                    "policy_gap": 2.5,
                    "institutional_relevance": 2.5,
                    "actionability": 2.5,
                    "evidence_maturity": 2.5,
                    "timing": 2.5,
                },
                "level": "Media",
                "rationale": "Razon oportunidad",
                "suggested_action": "Accion",
                "evidence_ids": ["ev-policy"],
                "confidence": "Alta",
            }
        ],
        "alignment_assessments": [
            {
                "temporary_id": "alignment-1",
                "theme_id": "theme-1",
                "pmge_project_ids": ["pmge-project-1"],
                "dimensions": {
                    "objective_match": 0,
                    "activity_match": 0,
                    "deliverable_match": 0,
                    "temporal_match": 0,
                    "evidence_strength": 0,
                },
                "level": "Baja",
                "rationale": "Razon alineacion",
                "alignment_type": "weak",
                "evidence_ids": ["ev-plan"],
                "confidence": "Alta",
            }
        ],
    }


def scored_strategic_payload() -> dict:
    payload = strategic_payload()
    payload["importance_assessments"][0]["importance_score"] = 84.0
    payload["opportunity_assessments"][0]["opportunity_score"] = 50.0
    payload["alignment_assessments"][0]["alignment_score"] = 0.0
    return payload


def make_workflow(
    client: FakeTransversalClient | None = None,
    scorer=None,
    use_empty_strategic_assessment: bool = False,
):
    snapshot_repo = InMemoryCorpusSnapshotRepository()
    analysis_repo = InMemoryAnalysisRunRepository(
        uuid_factory=uuid_factory(), clock=lambda: NOW
    )
    client = client or FakeTransversalClient()
    workflow = TransversalAnalysisWorkflow(
        snapshot_builder=CorpusSnapshotBuilder(
            snapshot_repo, uuid_factory=lambda: "snapshot-1", clock=lambda: NOW
        ),
        context_builder=CorpusContextBuilder(),
        extraction_service=StructuredExtractionService(client=client),
        analysis_run_repository=analysis_repo,
        strategic_assessment_scorer=scorer,
        use_empty_strategic_assessment=use_empty_strategic_assessment,
    )
    return workflow, snapshot_repo, analysis_repo, client


def uuid_factory():
    counter = {"value": 0}

    def next_uuid() -> str:
        counter["value"] += 1
        return f"run-uuid-{counter['value']}"

    return next_uuid


def test_full_flow_creates_snapshot_and_publishes_run():
    docs, bundles = fixtures()
    workflow, snapshot_repo, analysis_repo, client = make_workflow()

    result = workflow.run(documents=docs, bundles=bundles)

    assert result.snapshot.id == "snapshot-1"
    assert snapshot_repo.get_snapshot("snapshot-1") == result.snapshot
    assert result.run.status == AnalysisRunStatus.PUBLISHED
    assert analysis_repo.get_latest_published_run() == result.run
    assert [call["contract"] for call in client.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
        "StrategicAssessment",
    ]


def test_prompts_versions_contracts_and_stage_results_are_frozen():
    docs, bundles = fixtures()
    workflow, _, analysis_repo, _ = make_workflow()

    result = workflow.run(documents=docs, bundles=bundles, auto_publish=False)
    stages = analysis_repo.list_stages(result.run.id)

    assert result.run.status == AnalysisRunStatus.COMPLETED
    assert [(s.prompt_id, s.prompt_version, s.contract_name) for s in stages] == [
        ("thematic_landscape", "v1", "ThematicLandscape"),
        ("regulatory_intelligence", "v1", "RegulatoryIntelligence"),
        ("strategic_assessment", "v1", "StrategicAssessment"),
    ]
    assert stages[0].result_payload == thematic_payload()
    assert stages[1].result_payload == regulatory_payload()
    assert stages[2].result_payload == scored_strategic_payload()


def test_contexts_are_text_json_and_dependent_stages_receive_thematic_result():
    docs, bundles = fixtures()
    workflow, _, _, client = make_workflow()

    workflow.run(documents=docs, bundles=bundles)
    thematic_context = json.loads(client.calls[0]["text"])
    regulatory_context = json.loads(client.calls[1]["text"])
    strategic_context = json.loads(client.calls[2]["text"])

    assert thematic_context["findings"][0]["id"] == "finding-1"
    assert "agenda_regulatoria" in regulatory_context
    assert regulatory_context["thematic_landscape"] == thematic_payload()
    assert strategic_context["thematic_landscape"] == thematic_payload()
    assert "opportunity_inputs" in strategic_context
    for call in client.calls:
        assert call["input_data"].file_bytes is None
        assert call["input_data"].mime_type is None
        assert "file_hash" not in call["text"]
        assert "storage_path" not in call["text"]
        assert "chunks" not in call["text"]


def test_strategic_scores_are_saved_after_validation_without_mutating_client_payload():
    docs, bundles = fixtures()
    client = FakeTransversalClient()
    raw_response = strategic_payload()
    scorer = SpyScorer()
    workflow, _, analysis_repo, _ = make_workflow(client, scorer=scorer)

    result = workflow.run(documents=docs, bundles=bundles, auto_publish=False)
    stage = analysis_repo.get_stage(result.run.id, AnalysisStage.STRATEGIC_ASSESSMENT)

    assert stage.result_payload["importance_assessments"][0]["importance_score"] == 84.0
    assert stage.result_payload["opportunity_assessments"][0]["opportunity_score"] == 50.0
    assert stage.result_payload["alignment_assessments"][0]["alignment_score"] == 0.0
    assert stage.result_payload["importance_assessments"][0]["dimensions"] == (
        raw_response["importance_assessments"][0]["dimensions"]
    )
    assert stage.result_payload["importance_assessments"][0]["rationale"] == "Razon"
    assert stage.result_payload["importance_assessments"][0]["evidence_ids"] == ["ev-1"]
    assert scorer.calls == [raw_response]
    assert strategic_payload() == raw_response
    assert [call["contract"] for call in client.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
        "StrategicAssessment",
    ]


def test_scorer_runs_after_validation_only():
    docs, bundles = fixtures()
    invalid_client = FakeTransversalClient()
    scorer = SpyScorer()

    def invalid_generate_json(*, prompt, input_data, response_schema):
        invalid_client.calls.append(
            {
                "contract": response_schema["title"],
                "input_data": input_data,
                "text": input_data.text,
                "prompt": prompt,
            }
        )
        if response_schema["title"] == "StrategicAssessment":
            payload = strategic_payload()
            payload["importance_assessments"][0]["dimensions"]["ane_relevance"] = 9
            return payload
        return {
            "ThematicLandscape": thematic_payload(),
            "RegulatoryIntelligence": regulatory_payload(),
        }[response_schema["title"]]

    invalid_client.generate_json = invalid_generate_json
    workflow, _, _, _ = make_workflow(invalid_client, scorer=scorer)

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles)

    assert exc.value.stage == AnalysisStage.STRATEGIC_ASSESSMENT.value
    assert scorer.calls == []


def test_invalid_strategic_json_uses_empty_fallback_without_fabricating_scores():
    docs, bundles = fixtures()
    client = FakeTransversalClient()

    def invalid_strategic_json(*, prompt, input_data, response_schema):
        client.calls.append(
            {
                "contract": response_schema["title"],
                "input_data": input_data,
                "text": input_data.text,
                "prompt": prompt,
            }
        )
        if response_schema["title"] == "StrategicAssessment":
            raise InvalidLLMJSONError("json truncado")
        return {
            "ThematicLandscape": thematic_payload(),
            "RegulatoryIntelligence": regulatory_payload(),
        }[response_schema["title"]]

    client.generate_json = invalid_strategic_json
    workflow, _, analysis_repo, _ = make_workflow(client)

    result = workflow.run(documents=docs, bundles=bundles)

    assert result.run.status == AnalysisRunStatus.PUBLISHED
    strategic = analysis_repo.get_stage(
        result.run.id, AnalysisStage.STRATEGIC_ASSESSMENT
    )
    assert strategic.result_payload == {
        "importance_assessments": [],
        "opportunity_assessments": [],
        "alignment_assessments": [],
    }


def test_empty_strategic_flag_skips_llm_call_and_publishes_without_scores():
    docs, bundles = fixtures()
    workflow, _, analysis_repo, client = make_workflow(
        use_empty_strategic_assessment=True
    )

    result = workflow.run(documents=docs, bundles=bundles)

    assert result.run.status == AnalysisRunStatus.PUBLISHED
    assert [call["contract"] for call in client.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
    ]
    strategic = analysis_repo.get_stage(
        result.run.id, AnalysisStage.STRATEGIC_ASSESSMENT
    )
    assert strategic.result_payload == {
        "importance_assessments": [],
        "opportunity_assessments": [],
        "alignment_assessments": [],
    }


@pytest.mark.parametrize(
    ("contract", "expected_calls", "failed_stage"),
    [
        ("ThematicLandscape", [], AnalysisStage.THEMATIC_LANDSCAPE),
        (
            "RegulatoryIntelligence",
            ["ThematicLandscape"],
            AnalysisStage.REGULATORY_INTELLIGENCE,
        ),
        (
            "StrategicAssessment",
            ["ThematicLandscape", "RegulatoryIntelligence"],
            AnalysisStage.STRATEGIC_ASSESSMENT,
        ),
    ],
)
def test_stage_failure_stops_later_stages_and_does_not_publish(
    contract, expected_calls, failed_stage
):
    docs, bundles = fixtures()
    workflow, _, analysis_repo, client = make_workflow(
        FakeTransversalClient(fail_on=contract)
    )

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles)

    assert exc.value.stage == failed_stage.value
    assert exc.value.run_id is not None
    assert exc.value.snapshot_id == "snapshot-1"
    assert "file_hash" not in str(exc.value)
    assert [call["contract"] for call in client.calls] == [
        *expected_calls,
        contract,
    ]
    run = analysis_repo.get_run(exc.value.run_id)
    assert run.status == AnalysisRunStatus.FAILED
    assert analysis_repo.get_stage(run.id, failed_stage).status == AnalysisRunStatus.FAILED
    assert analysis_repo.get_latest_published_run() is None


def test_scoring_failure_fails_strategic_stage_and_does_not_publish():
    docs, bundles = fixtures()
    scorer = SpyScorer(fail=True)
    workflow, _, analysis_repo, client = make_workflow(scorer=scorer)

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles)

    assert exc.value.stage == AnalysisStage.STRATEGIC_ASSESSMENT.value
    assert "importance_assessments" not in str(exc.value)
    run = analysis_repo.get_run(exc.value.run_id)
    assert run.status == AnalysisRunStatus.FAILED
    assert (
        analysis_repo.get_stage(run.id, AnalysisStage.STRATEGIC_ASSESSMENT).status
        == AnalysisRunStatus.FAILED
    )
    assert analysis_repo.get_latest_published_run() is None
    assert [call["contract"] for call in client.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
        "StrategicAssessment",
    ]


def test_retry_does_not_repeat_completed_stages_and_reexecutes_dependents():
    docs, bundles = fixtures()
    failing = FakeTransversalClient(fail_on="RegulatoryIntelligence")
    workflow, snapshot_repo, analysis_repo, _ = make_workflow(failing)

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles, auto_publish=False)
    run_id = exc.value.run_id
    assert [call["contract"] for call in failing.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
    ]

    retry_client = FakeTransversalClient()
    retry_workflow = TransversalAnalysisWorkflow(
        snapshot_builder=workflow._snapshot_builder,
        context_builder=CorpusContextBuilder(),
        extraction_service=StructuredExtractionService(client=retry_client),
        analysis_run_repository=analysis_repo,
    )
    snapshot = snapshot_repo.get_snapshot("snapshot-1")

    result = retry_workflow.retry(
        run_id=run_id,
        snapshot=snapshot,
        documents=docs,
        bundles=bundles,
        auto_publish=False,
    )

    assert [call["contract"] for call in retry_client.calls] == [
        "RegulatoryIntelligence",
        "StrategicAssessment",
    ]
    assert result.run.status == AnalysisRunStatus.COMPLETED
    assert all(stage.status == AnalysisRunStatus.COMPLETED for stage in result.stages)


def test_retry_after_scoring_failure_reexecutes_only_strategic_assessment():
    docs, bundles = fixtures()
    failing_scorer = SpyScorer(fail=True)
    workflow, snapshot_repo, analysis_repo, client = make_workflow(
        scorer=failing_scorer
    )

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles, auto_publish=False)

    retry_client = FakeTransversalClient()
    retry_workflow = TransversalAnalysisWorkflow(
        snapshot_builder=workflow._snapshot_builder,
        context_builder=CorpusContextBuilder(),
        extraction_service=StructuredExtractionService(client=retry_client),
        analysis_run_repository=analysis_repo,
        strategic_assessment_scorer=SpyScorer(),
    )
    result = retry_workflow.retry(
        run_id=exc.value.run_id,
        snapshot=snapshot_repo.get_snapshot("snapshot-1"),
        documents=docs,
        bundles=bundles,
        auto_publish=False,
    )

    assert [call["contract"] for call in client.calls] == [
        "ThematicLandscape",
        "RegulatoryIntelligence",
        "StrategicAssessment",
    ]
    assert [call["contract"] for call in retry_client.calls] == [
        "StrategicAssessment"
    ]
    assert result.run.status == AnalysisRunStatus.COMPLETED
    assert result.results[AnalysisStage.STRATEGIC_ASSESSMENT].payload == (
        scored_strategic_payload()
    )


def test_publication_is_atomic_and_keeps_previous_published_history():
    docs, bundles = fixtures()
    workflow, _, analysis_repo, _ = make_workflow()
    first = workflow.run(documents=docs, bundles=bundles)

    second_workflow, _, _, _ = make_workflow()
    second_workflow._analysis_runs = analysis_repo
    second = second_workflow.run(documents=docs, bundles=bundles, snapshot=first.snapshot)

    assert analysis_repo.get_latest_published_run() == second.run
    assert analysis_repo.get_run(first.run.id).status == AnalysisRunStatus.PUBLISHED


def test_rejects_concurrent_execution_for_same_snapshot():
    docs, bundles = fixtures()
    workflow, _, analysis_repo, _ = make_workflow()
    snapshot = workflow._snapshot_builder.build_snapshot(documents=docs, bundles=bundles)
    analysis_repo.create_run(snapshot.id)

    with pytest.raises(TransversalAnalysisWorkflowError) as exc:
        workflow.run(documents=docs, bundles=bundles, snapshot=snapshot)

    assert isinstance(exc.value.original_error, ConcurrentAnalysisRunError)
    assert not workflow._extraction_service._client.calls
