"""Pruebas del runner por manifiesto de corpus."""

from pathlib import Path

from run_corpus_manifest_batch import main, read_manifest, select_manifest_rows


def test_select_manifest_rows_filters_batch_and_window():
    rows = [
        {"path": "a.pdf", "batch_id": "batch-001"},
        {"path": "b.pdf", "batch_id": "batch-001"},
        {"path": "c.pdf", "batch_id": "batch-002"},
    ]

    selected = select_manifest_rows(rows, batch_id="batch-001", offset=1, limit=1)

    assert selected == [{"path": "b.pdf", "batch_id": "batch-001"}]


def test_read_manifest_uses_utf8_sig(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "path,relative_path,source_type,provider,priority,batch_id,status,notes\n"
        "doc.pdf,doc.pdf,surveillance,CRC,2,batch-001,pending,ok\n",
        encoding="utf-8-sig",
    )

    assert read_manifest(manifest)[0]["source_type"] == "surveillance"


def test_main_dry_run_does_not_build_workflow(tmp_path: Path, monkeypatch, capsys):
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "path,relative_path,source_type,provider,priority,batch_id,status,notes\n"
        f"{doc},doc.pdf,surveillance,CRC,2,batch-001,pending,ok\n",
        encoding="utf-8-sig",
    )

    def fail_if_called(_settings=None):
        raise AssertionError("No debe construir workflow en dry-run")

    monkeypatch.setattr(
        "run_corpus_manifest_batch.build_manual_processing_workflow",
        fail_if_called,
    )

    exit_code = main([str(manifest), "--batch-id", "batch-001", "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Filas detectadas (1)" in output
    assert "[surveillance]" in output
