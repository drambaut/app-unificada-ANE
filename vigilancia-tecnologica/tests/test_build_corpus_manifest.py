"""Pruebas del generador de manifiesto de corpus."""

from pathlib import Path

from build_corpus_manifest import (
    build_manifest_rows,
    classify_file,
    discover_manifest_files,
    provider_from_relative_path,
    write_manifest,
)


def test_discover_manifest_files_lists_only_supported_files(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    xlsx = tmp_path / "matriz.xlsx"
    pptx = tmp_path / "presentacion.pptx"
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_pdf = nested / "otro.pdf"
    for path in (pdf, xlsx, pptx, nested_pdf):
        path.write_bytes(b"contenido")

    assert discover_manifest_files(tmp_path) == [
        pdf.resolve(),
        xlsx.resolve(),
        nested_pdf.resolve(),
    ]


def test_classify_known_institutional_files():
    assert classify_file(
        Path("Politicas Nacionales/PMGE20262030yAgendaRegulatoriaANE_Mar2026.pdf")
    )[0] == "institutional_plan"
    assert classify_file(
        Path("Politicas Nacionales/Plan Estrategico 2025-2028 con planes tactico.xlsx")
    )[0] == "policy_matrix"
    assert classify_file(Path("Cullen International/reporte.pdf"))[0] == "surveillance"


def test_build_manifest_rows_assigns_batches_and_provider(tmp_path: Path):
    root = tmp_path / "corpus"
    provider = root / "Cullen International"
    provider.mkdir(parents=True)
    files = []
    for index in range(3):
        path = provider / f"doc-{index}.pdf"
        path.write_bytes(b"pdf")
        files.append(path.resolve())

    rows = build_manifest_rows(root, files, batch_size=2)

    assert [row.batch_id for row in rows] == ["batch-001", "batch-001", "batch-002"]
    assert {row.provider for row in rows} == {"Cullen International"}
    assert {row.status for row in rows} == {"pending"}


def test_write_manifest_outputs_expected_columns(tmp_path: Path):
    root = tmp_path / "corpus"
    root.mkdir()
    path = root / "doc.pdf"
    path.write_bytes(b"pdf")
    rows = build_manifest_rows(root, [path.resolve()], batch_size=10)
    output = tmp_path / "manifest.csv"

    write_manifest(output, rows)

    content = output.read_text(encoding="utf-8-sig")
    assert "relative_path" in content
    assert "source_type" in content
    assert "batch-001" in content


def test_provider_from_single_file_path():
    assert provider_from_relative_path(Path("doc.pdf")) == "root"
