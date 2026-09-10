"""Ejecuta analisis transversal usando corpus procesado en Supabase."""

from __future__ import annotations

import argparse
from typing import Sequence

from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository
from app.core.settings import Settings, load_settings
from app.corpus_snapshots.builder import CorpusSnapshotBuilder
from app.corpus_snapshots.context_builder import CorpusContextBuilder
from app.corpus_snapshots.supabase_repository import SupabaseCorpusSnapshotRepository
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.llm.gemini_client import GeminiStructuredClient
from app.llm.service import StructuredExtractionService
from app.results.supabase_repository import SupabaseResultRepository
from app.workflows.supabase_transversal import SupabaseTransversalAnalysisWorkflow
from app.workflows.supabase_transversal import SupabaseTransversalAnalysisWorkflowError
from app.workflows.transversal_analysis import TransversalAnalysisWorkflow


def build_supabase_transversal_workflow(
    settings: Settings | None = None,
    *,
    max_records_by_type: dict[str, int] | None = None,
    use_empty_strategic_assessment: bool = False,
) -> SupabaseTransversalAnalysisWorkflow:
    settings = settings or load_settings()
    snapshot_repository = SupabaseCorpusSnapshotRepository(settings=settings)
    analysis_run_repository = SupabaseAnalysisRunRepository(settings=settings)
    transversal_workflow = TransversalAnalysisWorkflow(
        snapshot_builder=CorpusSnapshotBuilder(snapshot_repository),
        context_builder=CorpusContextBuilder(max_records_by_type=max_records_by_type),
        extraction_service=StructuredExtractionService(
            client=GeminiStructuredClient(settings=settings)
        ),
        analysis_run_repository=analysis_run_repository,
        use_empty_strategic_assessment=use_empty_strategic_assessment,
    )
    return SupabaseTransversalAnalysisWorkflow(
        document_repository=SupabaseDocumentRepository(settings=settings),
        result_repository=SupabaseResultRepository(settings=settings),
        snapshot_repository=snapshot_repository,
        analysis_run_repository=analysis_run_repository,
        transversal_workflow=transversal_workflow,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    bounded_context = args.bounded_context or args.demo
    max_records_by_type = (
        _bounded_context_limits() if bounded_context else _limits_from_args(args.limit)
    )
    metadata = {"trigger": "run_supabase_transversal.py"}
    if bounded_context:
        metadata["mode"] = "bounded_context"
    if max_records_by_type:
        metadata["context_limits"] = ",".join(
            f"{key}:{value}" for key, value in sorted(max_records_by_type.items())
        )
    try:
        workflow = build_supabase_transversal_workflow(
            max_records_by_type=max_records_by_type,
            use_empty_strategic_assessment=args.empty_strategic_assessment,
        )
        if args.retry_active:
            result = workflow.retry_latest_active(auto_publish=True)
        elif args.retry_run:
            result = workflow.retry_run(args.retry_run, auto_publish=True)
        else:
            result = workflow.run(
                metadata=metadata,
                auto_publish=True,
            )
    except SupabaseTransversalAnalysisWorkflowError as exc:
        print(f"No se pudo ejecutar fase 7: {exc}")
        return 1
    print(
        "Analisis transversal publicado: "
        f"snapshot={result.snapshot.id} run={result.run.id} status={result.run.status.value}"
    )
    return 0


def _bounded_context_limits() -> dict[str, int]:
    return {
        "documents": 6,
        "document_analysis": 6,
        "findings": 10,
        "evidence": 12,
        "initiatives": 4,
        "deliverables": 6,
        "policies": 4,
        "policy_activities": 6,
        "policy_commitments": 6,
    }


def _limits_from_args(raw_limits: Sequence[str]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for raw_limit in raw_limits:
        if "=" not in raw_limit:
            raise ValueError(f"Limite invalido '{raw_limit}'. Use nombre=numero.")
        key, raw_value = raw_limit.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Limite invalido '{raw_limit}'. La clave esta vacia.")
        value = int(raw_value)
        if value <= 0:
            raise ValueError(f"Limite invalido para {key}: debe ser mayor que cero.")
        limits[key] = value
    return limits


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta analisis transversal usando corpus procesado en Supabase."
    )
    parser.add_argument(
        "--bounded-context",
        action="store_true",
        help="Usa limites conservadores de contexto para corpus grandes.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--limit",
        action="append",
        default=[],
        help="Limite de contexto por lista, formato nombre=numero. Se puede repetir.",
    )
    parser.add_argument(
        "--empty-strategic-assessment",
        action="store_true",
        help=(
            "Completa strategic_assessment con listas vacias sin llamar Gemini. "
            "Usar solo cuando no haya cupo Gemini y ya existan etapas previas."
        ),
    )
    retry_group = parser.add_mutually_exclusive_group()
    retry_group.add_argument(
        "--retry-active",
        action="store_true",
        help="Reintenta la ejecucion activa mas reciente si una corrida anterior quedo bloqueada.",
    )
    retry_group.add_argument(
        "--retry-run",
        help="Reintenta una ejecucion transversal especifica por ID.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
