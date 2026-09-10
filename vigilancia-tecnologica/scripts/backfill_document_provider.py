"""Rellena la columna provider de documentos ya procesados, usando el manifiesto local.

Solo actualiza documentos que todavia no tienen provider guardado. Requiere
outputs/corpus_processing_manifest.csv (generado por build_corpus_manifest.py)
para mapear file_name -> provider. Documentos subidos manualmente desde el
dashboard que no aparezcan en el manifiesto quedan sin cambios.

Uso:
    python scripts/backfill_document_provider.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.settings import load_settings
from app.dashboard_data_builder import _load_provider_lookup
from app.documents.supabase_repository import SupabaseDocumentRepository


def main() -> None:
    settings = load_settings()
    repository = SupabaseDocumentRepository(settings=settings)
    provider_lookup = _load_provider_lookup()
    if not provider_lookup:
        print("No se encontro outputs/corpus_processing_manifest.csv; nada que hacer.")
        return

    documents = repository.list_processed_documents()
    updated = 0
    skipped_has_provider = 0
    skipped_no_match = 0
    for document in documents:
        if document.provider:
            skipped_has_provider += 1
            continue
        provider = provider_lookup.get(document.file_name)
        if not provider:
            skipped_no_match += 1
            continue
        repository.update_document_provider(document.id, provider)
        updated += 1
        print(f"[OK] {document.file_name}: provider={provider}")

    print(
        f"Actualizados: {updated} | ya tenian provider: {skipped_has_provider} | "
        f"sin match en manifiesto: {skipped_no_match}"
    )


if __name__ == "__main__":
    main()
