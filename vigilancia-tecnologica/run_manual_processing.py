"""Carga y procesa documentos reales en Supabase.

Uso tipico:
    python run_manual_processing.py ruta/al/documento.pdf --source-type surveillance
    python run_manual_processing.py ruta/al/corpus --source-type surveillance --recursive
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence
from uuid import uuid4

from app.core.settings import Settings, load_settings
from app.documents.models import (
    DocumentStatus,
    JobStatus,
    JobType,
    ProcessingJob,
    SourceType,
)
from app.documents.service import DocumentService
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.evidence.service import EvidenceValidationWorkflow
from app.evidence.validator import EvidenceValidator
from app.llm.gemini_client import GeminiStructuredClient
from app.llm.service import StructuredExtractionService
from app.preparation.service import DocumentPreparationService
from app.results.normalizer import ResultNormalizer
from app.results.service import ResultPersistenceService
from app.results.supabase_repository import SupabaseResultRepository
from app.storage.supabase_storage import SupabaseSourceDocumentStorage
from app.workflows.document_analysis import DocumentAnalysisWorkflow
from app.workflows.manual_processing import (
    ManualDocumentProcessingWorkflow,
    ManualDocumentProcessingWorkflowError,
)
from app.workflows.manual_upload import ManualDocumentUploadService


SUPPORTED_SUFFIXES = {".pdf", ".xls", ".xlsx"}


@dataclass(frozen=True)
class ProcessingReportRow:
    path: str
    file_name: str
    source_type: str
    batch_id: str
    status: str
    document_id: str
    stage: str
    error: str


def build_manual_processing_workflow(
    settings: Settings | None = None,
) -> ManualDocumentProcessingWorkflow:
    """Ensambla el workflow real: Storage, PostgreSQL, Gemini y persistencia."""
    settings = settings or load_settings()
    document_repository = SupabaseDocumentRepository(settings=settings)
    document_service = DocumentService(document_repository)
    upload_service = ManualDocumentUploadService(
        document_repository=document_repository,
        document_service=document_service,
        storage=SupabaseSourceDocumentStorage(settings=settings),
    )
    analysis_workflow = DocumentAnalysisWorkflow(
        document_service=document_service,
        preparation_service=DocumentPreparationService(document_repository),
        extraction_service=StructuredExtractionService(
            client=GeminiStructuredClient(settings=settings)
        ),
        repository=document_repository,
    )
    return ManualDocumentProcessingWorkflow(
        upload_service=upload_service,
        analysis_workflow=analysis_workflow,
        evidence_workflow=EvidenceValidationWorkflow(
            repository=document_repository,
            validator=EvidenceValidator(),
        ),
        persistence_service=ResultPersistenceService(
            document_repository=document_repository,
            result_repository=SupabaseResultRepository(settings=settings),
            normalizer=ResultNormalizer(),
        ),
        document_repository=document_repository,
    )


def discover_input_files(paths: Iterable[Path], *, recursive: bool = False) -> list[Path]:
    """Devuelve PDF/Excel soportados, deduplicados y ordenados."""
    discovered: dict[Path, Path] = {}
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved.is_file():
            _add_supported_file(discovered, resolved, explicit=True)
            continue
        if resolved.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in resolved.glob(pattern):
                if candidate.is_file():
                    _add_supported_file(discovered, candidate.resolve(), explicit=False)
            continue
        raise FileNotFoundError(f"No existe la ruta: {path}")
    return [discovered[key] for key in sorted(discovered)]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    source_type = SourceType(args.source_type)
    files = select_batch(
        discover_input_files(args.paths, recursive=args.recursive),
        offset=args.offset,
        limit=args.limit,
    )
    if not files:
        print("No se encontraron PDF/Excel para procesar.")
        return 1

    metadata = _metadata_from_args(args.metadata)
    if args.batch_id:
        metadata["batch_id"] = args.batch_id
    if args.dry_run:
        print(f"Archivos detectados ({len(files)}):")
        for file_path in files:
            print(f"- {file_path}")
        return 0

    settings = load_settings()
    workflow = build_manual_processing_workflow(settings)
    document_repository = SupabaseDocumentRepository(settings=settings)
    processed = 0
    failed = 0
    skipped = 0
    report_rows: list[ProcessingReportRow] = []
    for file_path in files:
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
                status = (
                    existing_document.status.value
                    if isinstance(existing_document.status, DocumentStatus)
                    else str(existing_document.status)
                )
                print(
                    "[SKIP] "
                    f"{file_path.name}: document_id={existing_document.id} "
                    f"status={status}"
                )
                report_rows.append(
                    ProcessingReportRow(
                        path=str(file_path),
                        file_name=file_path.name,
                        source_type=source_type.value,
                        batch_id=args.batch_id or "",
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
                    "origin": "run_manual_processing.py",
                    "local_path": str(file_path),
                    **metadata,
                },
                content_type=_guess_content_type(file_path),
                reuse_uploaded_duplicate=args.reset_failed,
            )
        except ManualDocumentProcessingWorkflowError as exc:
            failed += 1
            print(f"[ERROR] {file_path.name}: {exc}")
            report_rows.append(
                ProcessingReportRow(
                    path=str(file_path),
                    file_name=file_path.name,
                    source_type=source_type.value,
                    batch_id=args.batch_id or "",
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
                ProcessingReportRow(
                    path=str(file_path),
                    file_name=file_path.name,
                    source_type=source_type.value,
                    batch_id=args.batch_id or "",
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
        status = (
            result.document.status.value
            if isinstance(result.document.status, DocumentStatus)
            else str(result.document.status)
        )
        print(
            f"[OK] {file_path.name}: document_id={result.document.id} status={status}"
        )
        report_rows.append(
            ProcessingReportRow(
                path=str(file_path),
                file_name=file_path.name,
                source_type=source_type.value,
                batch_id=args.batch_id or "",
                status=status,
                document_id=result.document.id,
                stage="completed",
                error="",
            )
        )

    if args.report_csv:
        write_report_csv(args.report_csv, report_rows)
        print(f"Reporte CSV: {args.report_csv}")

    print(
        "Resumen: "
        f"procesados={processed} fallidos={failed} "
        f"omitidos={skipped} total={len(files)}"
    )
    return 0 if failed == 0 else 1


def select_batch(files: Sequence[Path], *, offset: int = 0, limit: int | None = None) -> list[Path]:
    """Aplica ventana de lote deterministica a una lista de archivos."""
    if offset < 0:
        raise ValueError("--offset no puede ser negativo.")
    if limit is not None and limit < 1:
        raise ValueError("--limit debe ser mayor o igual a 1.")
    selected = list(files)[offset:]
    return selected[:limit] if limit is not None else selected


def find_existing_document(
    *,
    file_bytes: bytes,
    settings: Settings,
    repository: SupabaseDocumentRepository | None = None,
):
    repository = repository or SupabaseDocumentRepository(settings=settings)
    file_hash = DocumentService.calculate_sha256(file_bytes)
    return repository.find_document_by_hash(file_hash)


def should_skip_existing_document(
    document,
    *,
    skip_existing: bool,
    reset_failed: bool,
) -> bool:
    if document is None or not skip_existing:
        return False
    if reset_failed and document.status == DocumentStatus.FAILED:
        return False
    return True


def reset_failed_duplicate(
    *,
    file_name: str,
    file_bytes: bytes,
    source_type: SourceType,
    settings: Settings,
    repository: SupabaseDocumentRepository | None = None,
):
    """Reinicia un documento fallido para reintentar el pipeline completo."""
    repository = repository or SupabaseDocumentRepository(settings=settings)
    file_hash = DocumentService.calculate_sha256(file_bytes)
    document = repository.find_document_by_hash(file_hash)
    if document is None:
        return None
    if document.source_type != source_type:
        raise ValueError(
            f"{file_name} ya existe como {document.source_type.value}; "
            f"no se puede reintentar como {source_type.value}."
        )
    if document.status == DocumentStatus.PROCESSED:
        raise ValueError(f"{file_name} ya esta processed; no se resetea.")
    if document.status != DocumentStatus.FAILED:
        raise ValueError(
            f"{file_name} ya existe en estado {document.status.value}; "
            "solo se resetean documentos failed."
        )

    client = repository._client_instance()
    existing_results = (
        client.table("result_records")
        .select("id")
        .eq("document_id", document.id)
        .limit(1)
        .execute()
        .data
    )
    if existing_results:
        raise ValueError(
            f"{file_name} tiene resultados persistidos; no se resetea automaticamente."
        )

    client.table("document_chunks").delete().eq("document_id", document.id).execute()
    client.table("processing_jobs").delete().eq("document_id", document.id).execute()
    reset_document = repository.update_document_status(
        document.id, DocumentStatus.UPLOADED
    )
    repository.create_job(
        ProcessingJob(
            id=str(uuid4()),
            document_id=document.id,
            job_type=JobType.DOCUMENT_PREPARATION,
            status=JobStatus.QUEUED,
            prompt_id=None,
            prompt_version=None,
            attempts=0,
            error_message=None,
            created_at=datetime.now(UTC),
            completed_at=None,
        )
    )
    return reset_document


def write_report_csv(path: Path, rows: Sequence[ProcessingReportRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "file_name",
                "source_type",
                "batch_id",
                "status",
                "document_id",
                "stage",
                "error",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _add_supported_file(
    discovered: dict[Path, Path], path: Path, *, explicit: bool
) -> None:
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        if explicit:
            raise ValueError(
                f"Formato no soportado: {path.name}. Use PDF, XLS o XLSX."
            )
        return
    discovered[path] = path


def _metadata_from_args(raw_items: Sequence[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"Metadata invalida '{item}'. Use clave=valor.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Metadata invalida '{item}'. La clave esta vacia.")
        metadata[key] = value.strip()
    return metadata


def _guess_content_type(path: Path) -> str:
    if path.suffix.lower() == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if path.suffix.lower() == ".xls":
        return "application/vnd.ms-excel"
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga y procesa documentos reales en Supabase."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Archivos o carpetas con PDF/XLS/XLSX.",
    )
    parser.add_argument(
        "--source-type",
        choices=[item.value for item in SourceType],
        required=True,
        help="Tipo documental segun la arquitectura.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Buscar documentos dentro de subcarpetas.",
    )
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="Metadata adicional en formato clave=valor. Se puede repetir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo listar archivos detectados; no llama Supabase ni Gemini.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de archivos a procesar en esta corrida.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Cantidad de archivos ordenados a saltar antes de procesar.",
    )
    parser.add_argument(
        "--batch-id",
        default="",
        help="Identificador operativo del lote; se guarda en metadata y reporte.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Omitir archivos que ya existen en Supabase por hash.",
    )
    parser.add_argument(
        "--report-csv",
        type=Path,
        help="Ruta para escribir un reporte CSV de procesados, fallidos y omitidos.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Detener el lote ante el primer error.",
    )
    parser.add_argument(
        "--reset-failed",
        action="store_true",
        help=(
            "Si el archivo ya existe como failed, limpiar chunks/jobs y "
            "reintentar el procesamiento completo."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
