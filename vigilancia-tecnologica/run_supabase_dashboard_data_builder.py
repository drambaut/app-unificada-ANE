"""Regenera demo_data/ a partir de documentos ya procesados en Supabase.

No consume Gemini: reutiliza document_analysis ya persistido para cada
documento surveillance con status=processed. Requiere SUPABASE_URL y
SUPABASE_SERVICE_ROLE_KEY (o SUPABASE_KEY) configurados.

Uso:
    python run_supabase_dashboard_data_builder.py
"""

from __future__ import annotations

import logging

from app.dashboard_data_builder import build_dashboard_data_from_supabase


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = build_dashboard_data_from_supabase()
    print(f"Registros procesados: {result['records_processed']}")
    print(f"Temas estrategicos identificados: {result['strategic_topics']}")
    print(f"Senales generadas: {result['signals_generated']}")
    print(f"Archivos copiados a demo_data: {result['files_copied']}")
    print(f"Ruta de demo_data: {result['demo_data_dir']}")


if __name__ == "__main__":
    main()
