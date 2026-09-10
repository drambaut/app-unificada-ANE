"""Script manual para importar el corpus inicial de documentos.

Migra archivos existentes en `Vigilanciatecnologica_data/Vigilancia tecnologica`
hacia Supabase Storage y PostgreSQL, clasificándolos según el inventario.
"""

import sys
from pathlib import Path
from typing import Sequence

# Agregar el root al sys.path para poder importar `run_manual_processing`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_manual_processing import main as run_manual_processing_main


def _run_batch(paths: list[str], source_type: str) -> None:
    print(f"\n--- Iniciando lote: {source_type} ({len(paths)} rutas) ---")
    
    # Preparar los argumentos para el script de procesamiento
    args = [
        "--source-type", source_type,
        "--skip-existing",
        "--recursive",
        "--reset-failed",
        "--batch-id", "initial_corpus_import"
    ]
    args.extend(paths)
    
    try:
        run_manual_processing_main(args)
    except SystemExit as exc:
        if exc.code != 0:
            print(f"Advertencia: El lote {source_type} terminó con errores.")


def main(argv: Sequence[str] | None = None) -> int:
    base_dir = PROJECT_ROOT / "Vigilanciatecnologica_data" / "Vigilancia tecnológica"
    if not base_dir.is_dir():
        print(f"Error: No se encontró la carpeta base {base_dir}")
        return 1

    # Carpetas identificadas como surveillance
    surveillance_folders = [
        "CRC",
        "Cullen International",
        "ejercicio preliminar",
        "GSMA",
        "NERA",
        "Omdia",
        "PolicyTracker",
        "Reguladores",
        "UIT",
        "WorldBank",
    ]

    surveillance_paths = []
    for folder in surveillance_folders:
        path = base_dir / folder
        if path.exists():
            surveillance_paths.append(str(path))
        else:
            print(f"Advertencia: Carpeta surveillance no encontrada: {folder}")

    if surveillance_paths:
        _run_batch(surveillance_paths, "surveillance")

    # Documentos institucionales
    pmge_plan = base_dir / "Politicas Nacionales" / "PMGE20262030yAgendaRegulatoriaANE_Mar2026.pdf"
    if pmge_plan.exists():
        _run_batch([str(pmge_plan)], "institutional_plan")
    else:
        print("Advertencia: No se encontró el PMGE.")

    # Matriz de políticas y proyectos PMGE
    # Según INVENTARIO_CORPUS_INICIAL.md, esto está pendiente de confirmación.
    # Por ahora, solo indicamos que debe hacerse manualmente después de validar.
    policy_matrix = base_dir / "Politicas Nacionales" / "Plan Estrategico 2025-2028 con planes tactico.xlsx"
    print("\n--- Tareas manuales pendientes ---")
    if policy_matrix.exists():
        print(
            "Se encontró un posible candidato a matriz de políticas:\n"
            f"  {policy_matrix}\n"
            "Valida con el negocio antes de procesarlo:\n"
            f"  python run_manual_processing.py \"{policy_matrix}\" --source-type policy_matrix\n"
        )

    print("\nImportación inicial completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
