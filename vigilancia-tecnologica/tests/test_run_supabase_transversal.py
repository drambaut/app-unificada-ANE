"""Pruebas del runner de analisis transversal Supabase."""

from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository
from app.core.settings import load_settings
from app.corpus_snapshots.supabase_repository import SupabaseCorpusSnapshotRepository
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.results.supabase_repository import SupabaseResultRepository
from app.workflows.supabase_transversal import SupabaseTransversalAnalysisWorkflow
from run_supabase_transversal import (
    _bounded_context_limits,
    _limits_from_args,
    build_supabase_transversal_workflow,
)


def test_build_supabase_transversal_workflow_wires_real_adapters():
    settings = load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    workflow = build_supabase_transversal_workflow(settings)

    assert isinstance(workflow, SupabaseTransversalAnalysisWorkflow)
    assert isinstance(workflow._document_repository, SupabaseDocumentRepository)
    assert isinstance(workflow._result_repository, SupabaseResultRepository)
    transversal = workflow._transversal_workflow
    assert isinstance(
        transversal._snapshot_builder._repository,
        SupabaseCorpusSnapshotRepository,
    )
    assert isinstance(transversal._analysis_runs, SupabaseAnalysisRunRepository)


def test_build_supabase_transversal_workflow_accepts_context_limits():
    settings = load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    workflow = build_supabase_transversal_workflow(
        settings,
        max_records_by_type={"findings": 2},
    )

    context_builder = workflow._transversal_workflow._context_builder
    assert context_builder._max_records_by_type == {"findings": 2}


def test_build_supabase_transversal_workflow_accepts_empty_strategic_flag():
    settings = load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    workflow = build_supabase_transversal_workflow(
        settings,
        use_empty_strategic_assessment=True,
    )

    transversal = workflow._transversal_workflow
    assert transversal._use_empty_strategic_assessment is True


def test_bounded_context_limits_are_conservative_and_parse_custom_limits():
    assert _bounded_context_limits()["findings"] < 50
    assert _limits_from_args(["findings=3", "evidence=4"]) == {
        "findings": 3,
        "evidence": 4,
    }
