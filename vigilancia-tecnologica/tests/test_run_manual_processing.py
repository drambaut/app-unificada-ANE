"""Pruebas del runner de procesamiento manual Supabase."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.settings import load_settings
from app.documents.models import DocumentStatus, SourceType
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.results.supabase_repository import SupabaseResultRepository
from app.storage.supabase_storage import SupabaseSourceDocumentStorage
from app.workflows.manual_processing import ManualDocumentProcessingWorkflow
from run_manual_processing import (
    ProcessingReportRow,
    build_manual_processing_workflow,
    discover_input_files,
    _guess_content_type,
    main,
    select_batch,
    should_skip_existing_document,
    write_report_csv,
)


def test_build_manual_processing_workflow_wires_real_adapters():
    settings = load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    workflow = build_manual_processing_workflow(settings)

    assert isinstance(workflow, ManualDocumentProcessingWorkflow)
    assert isinstance(
        workflow._upload_service._document_repository,
        SupabaseDocumentRepository,
    )
    assert isinstance(workflow._upload_service._storage, SupabaseSourceDocumentStorage)
    assert isinstance(
        workflow._persistence_service._result_repository,
        SupabaseResultRepository,
    )


def test_discover_input_files_filters_supported_files(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    xlsx = tmp_path / "matriz.xlsx"
    txt = tmp_path / "nota.txt"
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_pdf = nested / "interno.pdf"
    for path in (pdf, xlsx, txt, nested_pdf):
        path.write_bytes(b"contenido")

    assert discover_input_files([tmp_path], recursive=False) == [pdf.resolve(), xlsx.resolve()]
    assert discover_input_files([tmp_path], recursive=True) == [
        pdf.resolve(),
        xlsx.resolve(),
        nested_pdf.resolve(),
    ]


def test_discover_input_files_rejects_explicit_unsupported_file(tmp_path: Path):
    text_file = tmp_path / "nota.txt"
    text_file.write_text("no soportado", encoding="utf-8")

    with pytest.raises(ValueError, match="Formato no soportado"):
        discover_input_files([text_file])


def test_guess_content_type_handles_excel_extensions(tmp_path: Path):
    assert _guess_content_type(tmp_path / "matriz.xlsx") == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert _guess_content_type(tmp_path / "legacy.xls") == "application/vnd.ms-excel"


def test_select_batch_applies_offset_and_limit(tmp_path: Path):
    files = [tmp_path / f"doc-{index}.pdf" for index in range(5)]

    assert select_batch(files, offset=1, limit=2) == files[1:3]
    assert select_batch(files, offset=3, limit=None) == files[3:]


def test_skip_existing_allows_failed_document_when_reset_failed():
    failed = SimpleNamespace(status=DocumentStatus.FAILED)
    processed = SimpleNamespace(status=DocumentStatus.PROCESSED)

    assert should_skip_existing_document(
        failed, skip_existing=True, reset_failed=True
    ) is False
    assert should_skip_existing_document(
        processed, skip_existing=True, reset_failed=True
    ) is True


def test_write_report_csv_creates_operational_summary(tmp_path: Path):
    report_path = tmp_path / "reports" / "batch.csv"

    write_report_csv(
        report_path,
        [
            ProcessingReportRow(
                path="doc.pdf",
                file_name="doc.pdf",
                source_type="surveillance",
                batch_id="pilot-01",
                status="processed",
                document_id="doc-1",
                stage="completed",
                error="",
            )
        ],
    )

    content = report_path.read_text(encoding="utf-8-sig")
    assert "batch_id" in content
    assert "pilot-01" in content
    assert "doc-1" in content


def test_main_dry_run_does_not_build_workflow(tmp_path: Path, monkeypatch, capsys):
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (tmp_path / name).write_bytes(b"%PDF")

    def fail_if_called():
        raise AssertionError("No debe construir workflow en dry-run")

    monkeypatch.setattr("run_manual_processing.build_manual_processing_workflow", fail_if_called)

    exit_code = main(
        [
            str(tmp_path),
            "--source-type",
            SourceType.SURVEILLANCE.value,
            "--dry-run",
            "--offset",
            "1",
            "--limit",
            "1",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Archivos detectados (1)" in output
    assert "b.pdf" in output
    assert "a.pdf" not in output
    assert "c.pdf" not in output
