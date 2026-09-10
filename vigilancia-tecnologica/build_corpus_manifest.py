r"""Genera un manifiesto CSV para procesar el corpus por lotes.

Uso:
    python build_corpus_manifest.py "Vigilanciatecnologica_data\Vigilancia tecnológica"
"""

from __future__ import annotations

import argparse
import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from run_manual_processing import SUPPORTED_SUFFIXES


DEFAULT_OUTPUT = Path("outputs/corpus_processing_manifest.csv")


@dataclass(frozen=True)
class ManifestRow:
    path: str
    relative_path: str
    source_type: str
    provider: str
    priority: int
    batch_id: str
    status: str
    notes: str


def discover_manifest_files(root: Path) -> list[Path]:
    """Lista archivos soportados por el pipeline actual."""
    resolved_root = root.expanduser().resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"No existe la carpeta: {root}")
    if not resolved_root.is_dir():
        raise ValueError(f"La ruta debe ser una carpeta: {root}")
    return sorted(
        path.resolve()
        for path in resolved_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def build_manifest_rows(
    root: Path, files: Iterable[Path], *, batch_size: int
) -> list[ManifestRow]:
    if batch_size < 1:
        raise ValueError("--batch-size debe ser mayor o igual a 1.")

    resolved_root = root.expanduser().resolve()
    candidates = []
    for path in files:
        relative = path.relative_to(resolved_root)
        source_type, priority, notes = classify_file(relative)
        candidates.append(
            {
                "path": path,
                "relative": relative,
                "source_type": source_type,
                "provider": provider_from_relative_path(relative),
                "priority": priority,
                "notes": notes,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["priority"],
            str(item["provider"]).casefold(),
            item["relative"].as_posix().casefold(),
        )
    )

    rows: list[ManifestRow] = []
    for index, item in enumerate(candidates):
        rows.append(
            ManifestRow(
                path=str(item["path"]),
                relative_path=item["relative"].as_posix(),
                source_type=str(item["source_type"]),
                provider=str(item["provider"]),
                priority=int(item["priority"]),
                batch_id=f"batch-{(index // batch_size) + 1:03d}",
                status="pending",
                notes=str(item["notes"]),
            )
        )
    return rows


def classify_file(relative_path: Path) -> tuple[str, int, str]:
    normalized = _normalize_path(relative_path)
    file_name = _normalize_text(relative_path.name)
    if "politicas nacionales" in normalized and "pmge" in file_name:
        return "institutional_plan", 1, "PMGE y Agenda Regulatoria ANE"
    if (
        "politicas nacionales" in normalized
        and "plan estrategico 2025-2028 con planes tactico" in file_name
    ):
        return "policy_matrix", 1, "Plan estrategico/tactico usado como policy_matrix"
    if "ejercicio preliminar" in normalized:
        return "surveillance", 1, "Matriz/noticias preliminares de vigilancia"
    return "surveillance", 2, "Documento de vigilancia"


def provider_from_relative_path(relative_path: Path) -> str:
    parts = relative_path.parts
    if len(parts) <= 1:
        return "root"
    return parts[0]


def write_manifest(path: Path, rows: Sequence[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "relative_path",
                "source_type",
                "provider",
                "priority",
                "batch_id",
                "status",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _normalize_path(path: Path) -> str:
    return _normalize_text(path.as_posix())


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.casefold()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera manifiesto CSV para procesar corpus por lotes."
    )
    parser.add_argument("root", type=Path, help="Carpeta raiz del corpus.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ruta CSV de salida. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Cantidad de archivos por lote operativo.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    files = discover_manifest_files(args.root)
    rows = build_manifest_rows(args.root, files, batch_size=args.batch_size)
    write_manifest(args.output, rows)
    print(f"Manifiesto generado: {args.output}")
    print(f"Archivos soportados: {len(rows)}")
    print(f"Lotes: {len({row.batch_id for row in rows})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
