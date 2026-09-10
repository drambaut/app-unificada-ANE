"""Procesa un lote desde el manifiesto de corpus.

Uso:
    python run_corpus_manifest_batch.py outputs/corpus_processing_manifest.csv --batch-id batch-001 --skip-existing
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

from app.core.settings import load_settings
from app.documents.models import DocumentStatus, SourceType
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.workflows.manual_processing import ManualDocumentProcessingWorkflowError
from run_manual_processing import (
    ProcessingReportRow,
    build_manual_processing_workflow,
    find_existing_document,
    _metadata_from_args,
    reset_failed_duplicate,
    should_skip_existing_document,
    write_report_csv,
    _guess_content_type,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    rows = select_manifest_rows(
        read_manifest(args.manifest),
        batch_id=args.batch_id,
        offset=args.offset,
        limit=args.limit,
    )
    if not rows:
        print("No hay filas del manifiesto para procesar.")
        return 1

    if args.dry_run:
        print(f"Filas detectadas ({len(rows)}):")
        for row in rows:
            print(f"- [{row['source_type']}] {row['path']}")
        return 0

    base_metadata = _metadata_from_args(args.metadata)
    if args.smoke:
        base_metadata["smoke"] = "true"

    settings = load_settings()
    workflow = build_manual_processing_workflow(settings)
    document_repository = SupabaseDocumentRepository(settings=settings)
    processed = 0
    failed = 0
    skipped = 0
    report_rows: list[ProcessingReportRow] = []

    for row in rows:
        file_path = Path(row["path"])
        source_type = SourceType(row["source_type"])
        file_bytes = file_path.read_bytes()
        existing_document = None
        try:
            existing_document = find_existing_document(
                file_bytes=file_bytes,
                settings=settings,
                repository=document_repository,
            )
            if should_skip_existing_document(
                existing_document,
                skip_existing=args.skip_existing,
                reset_failed=args.reset_failed,
            ):
                skipped += 1
                status = _status_value(existing_document.status)
                print(
                    "[SKIP] "
                    f"{file_path.name}: document_id={existing_document.id} "
                    f"status={status}"
                )
                report_rows.append(
                    _report_row(
                        row,
                        file_path=file_path,
                        status="skipped",
                        document_id=existing_document.id,
                        stage="preflight",
                        error=f"documento existente status={status}",
                    )
                )
                continue

            if args.reset_failed:
                reset_document = reset_failed_duplicate(
                    file_name=file_path.name,
                    file_bytes=file_bytes,
                    source_type=source_type,
                    settings=settings,
                    repository=document_repository,
                )
                if reset_document is not None:
                    print(
                        "[RESET] "
                        f"{file_path.name}: document_id={reset_document.id} "
                        "status=uploaded"
                    )

            result = workflow.run(
                file_name=file_path.name,
                file_bytes=file_bytes,
                source_type=source_type,
                metadata={
                    "origin": "run_corpus_manifest_batch.py",
                    "local_path": str(file_path),
                    "manifest_relative_path": row.get("relative_path", ""),
                    "provider": row.get("provider", ""),
                    "priority": row.get("priority", ""),
                    "batch_id": row.get("batch_id", ""),
                    **base_metadata,
                },
                content_type=_guess_content_type(file_path),
                reuse_uploaded_duplicate=args.reset_failed,
            )
        except ManualDocumentProcessingWorkflowError as exc:
            failed += 1
            print(f"[ERROR] {file_path.name}: {exc}")
            report_rows.append(
                _report_row(
                    row,
                    file_path=file_path,
                    status="failed",
                    document_id=exc.document_id or "",
                    stage=exc.stage,
                    error=str(exc.original_error),
                )
            )
            if args.stop_on_error:
                break
            continue
        except Exception as exc:
            failed += 1
            document_id = existing_document.id if existing_document is not None else ""
            print(f"[ERROR] {file_path.name}: {exc}")
            report_rows.append(
                _report_row(
                    row,
                    file_path=file_path,
                    status="failed",
                    document_id=document_id,
                    stage="preflight",
                    error=str(exc),
                )
            )
            if args.stop_on_error:
                break
            continue

        processed += 1
        status = _status_value(result.document.status)
        print(f"[OK] {file_path.name}: document_id={result.document.id} status={status}")
        report_rows.append(
            _report_row(
                row,
                file_path=file_path,
                status=status,
                document_id=result.document.id,
                stage="completed",
                error="",
            )
        )

    report_path = args.report_csv or Path(
        f"outputs/corpus_{args.batch_id or 'selected'}_report.csv"
    )
    write_report_csv(report_path, report_rows)
    print(f"Reporte CSV: {report_path}")
    print(
        "Resumen: "
        f"procesados={processed} fallidos={failed} omitidos={skipped} "
        f"total={len(rows)}"
    )
    return 0 if failed == 0 else 1


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def select_manifest_rows(
    rows: Sequence[dict[str, str]],
    *,
    batch_id: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[dict[str, str]]:
    if offset < 0:
        raise ValueError("--offset no puede ser negativo.")
    if limit is not None and limit < 1:
        raise ValueError("--limit debe ser mayor o igual a 1.")
    if batch_id:
        rows = [row for row in rows if row.get("batch_id") == batch_id]
    selected = list(rows)[offset:]
    return selected[:limit] if limit is not None else selected


def _report_row(
    row: dict[str, str],
    *,
    file_path: Path,
    status: str,
    document_id: str,
    stage: str,
    error: str,
) -> ProcessingReportRow:
    return ProcessingReportRow(
        path=str(file_path),
        file_name=file_path.name,
        source_type=row.get("source_type", ""),
        batch_id=row.get("batch_id", ""),
        status=status,
        document_id=document_id,
        stage=stage,
        error=error,
    )


def _status_value(status) -> str:
    return status.value if isinstance(status, DocumentStatus) else str(status)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Procesa un lote desde outputs/corpus_processing_manifest.csv."
    )
    parser.add_argument("manifest", type=Path, help="CSV generado por build_corpus_manifest.py.")
    parser.add_argument("--batch-id", default="", help="Batch a procesar, por ejemplo batch-001.")
    parser.add_argument("--limit", type=int, default=None, help="Maximo de filas del lote.")
    parser.add_argument("--offset", type=int, default=0, help="Filas del lote a saltar.")
    parser.add_argument("--dry-run", action="store_true", help="Lista filas sin llamar Supabase/Gemini.")
    parser.add_argument("--metadata", action="append", default=[], help="Metadata adicional clave=valor.")
    parser.add_argument("--smoke", action="store_true", help="Activa metadata smoke=true para extracciones acotadas.")
    parser.add_argument("--skip-existing", action="store_true", help="Omite documentos ya cargados por hash.")
    parser.add_argument("--reset-failed", action="store_true", help="Reintenta documentos fallidos existentes.")
    parser.add_argument("--stop-on-error", action="store_true", help="Detiene el lote ante el primer error.")
    parser.add_argument("--report-csv", type=Path, help="Ruta del reporte CSV de salida.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
