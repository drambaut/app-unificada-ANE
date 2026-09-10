"""Muestra estado de una ejecucion transversal en Supabase."""

from __future__ import annotations

import argparse
from typing import Sequence

from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = SupabaseAnalysisRunRepository()
    run = repository.get_run(args.run_id)
    if run is None:
        print(f"Run: {args.run_id} NO ENCONTRADO")
        return 1

    print(f"Run: {run.id}")
    print(f"Snapshot: {run.corpus_snapshot_id}")
    print(f"Status: {run.status.value}")
    print(f"Published at: {run.published_at or 'NO'}")
    print("Stages:")
    for stage in repository.list_stages(run.id):
        has_payload = "si" if stage.result_payload is not None else "no"
        print(
            f"- {stage.stage.value}: {stage.status.value} "
            f"payload={has_payload}"
        )
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta estado de una ejecucion transversal Supabase."
    )
    parser.add_argument("run_id")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
