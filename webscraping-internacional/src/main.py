"""
main.py
=======
Punto de entrada principal de la herramienta de búsqueda telecom.

Uso:
    python src/main.py --query "radio spectrum allocation"
    python src/main.py --query "gestión del espectro" --sites itu fcc ofcom
    python src/main.py --query "spectrum" --headless false --format csv
    python src/main.py --query "spectrum" --no-translate
    python src/main.py --list-sites

Opciones:
    --query          Término de búsqueda (requerido)
    --sites          IDs de sitios a buscar (default: todos)
    --headless       true/false - ocultar/mostrar navegador (default: true)
    --format         xlsx o csv (default: xlsx)
    --output-dir     Directorio de salida (default: output/)
    --max-links      Máx. links por sitio (default: 50)
    --no-translate   No traducir, solo usar la query tal como está
    --list-sites     Mostrar sitios disponibles y salir
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ─── Ajustar sys.path para importar módulos locales ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from browser import get_browser
from scraper import search_all_sites
from translator import translate_query
from exporter import export_to_excel, export_to_csv, print_summary


# ─── Configuración de Logging ────────────────────────────────────────────────
def setup_logging(log_dir: str = "logs") -> logging.Logger:
    """Configura logging a consola y archivo simultáneamente."""
    os.makedirs(log_dir, exist_ok=True)

    from datetime import datetime
    log_file = os.path.join(log_dir, f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return logging.getLogger("telecom_searcher")


# ─── Carga de configuración ──────────────────────────────────────────────────
def load_sites(config_path: str = None) -> list:
    """
    Carga la lista de sitios desde config/sites.json.

    Args:
        config_path: Ruta opcional al JSON. Si no se provee, busca relativo al script.

    Returns:
        Lista de dicts con la configuración de cada sitio.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "sites.json"

    with open(config_path, "r", encoding="utf-8") as f:
        sites = json.load(f)

    return sites


def filter_sites(sites: list, site_ids: list) -> list:
    """Filtra la lista de sitios por IDs especificados."""
    if not site_ids:
        return sites
    return [s for s in sites if s["id"] in site_ids]


# ─── Argparse ────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="🔍 Telecom Web Searcher - Búsqueda automatizada en reguladores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python src/main.py --query "radio spectrum allocation"
  python src/main.py --query "espectro radioeléctrico" --sites itu fcc ofcom
  python src/main.py --query "spectrum" --headless false
  python src/main.py --list-sites
        """,
    )

    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Término de búsqueda (obligatorio si no se usa --list-sites)"
    )
    parser.add_argument(
        "--sites", "-s",
        nargs="+",
        metavar="SITE_ID",
        help="IDs de sitios específicos (ej: itu fcc ofcom). Default: todos."
    )
    parser.add_argument(
        "--headless",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Ocultar navegador (true) o mostrarlo (false). Default: true."
    )
    parser.add_argument(
        "--format", "-f",
        type=str,
        default="xlsx",
        choices=["xlsx", "csv"],
        help="Formato de exportación. Default: xlsx."
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="output",
        help="Directorio de salida. Default: output/"
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=50,
        help="Máximo de links a guardar por sitio. Default: 50."
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="No traducir la query; usarla tal como está en todos los sitios."
    )
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="Mostrar los sitios configurados y salir."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta personalizada al archivo sites.json."
    )

    return parser.parse_args()


# ─── Función principal ────────────────────────────────────────────────────────
async def main():
    args = parse_args()
    logger = setup_logging()

    # Cargar sitios
    try:
        all_sites = load_sites(args.config)
    except FileNotFoundError as e:
        print(f"❌ Error: No se encontró config/sites.json: {e}")
        sys.exit(1)

    # Mostrar sitios disponibles
    if args.list_sites:
        print("\n📋 Sitios configurados:\n")
        for s in all_sites:
            print(f"  [{s['id']:8s}] {s['name']}")
            print(f"             URL: {s['url']}")
            print(f"             Idioma: {s['language']} | Región: {s['region']}")
            print()
        return

    # Validar que se proporcionó una query
    if not args.query:
        print("❌ Error: Debes proporcionar --query. Usa --help para ver las opciones.")
        sys.exit(1)

    query = args.query.strip()
    headless = args.headless.lower() == "true"
    sites = filter_sites(all_sites, args.sites)

    if not sites:
        print(f"❌ Error: Ningún sitio válido encontrado con IDs: {args.sites}")
        sys.exit(1)

    # ─── Banner de inicio ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  🛰️  TELECOM WEB SEARCHER")
    print("=" * 60)
    print(f"  Query:      {query}")
    print(f"  Sitios:     {len(sites)} de {len(all_sites)}")
    print(f"  Navegador:  {'invisible (headless)' if headless else 'visible'}")
    print(f"  Formato:    {args.format.upper()}")
    print(f"  Traducción: {'desactivada' if args.no_translate else 'automática (en/es/ko/pt)'}")
    print("=" * 60 + "\n")

    # ─── Traducción ───────────────────────────────────────────────────────────
    if args.no_translate:
        translations = {"original": query, "en": query, "es": query, "ko": query, "pt": query}
        logger.info("Traducción desactivada. Usando query original en todos los sitios.")
    else:
        logger.info("Traduciendo query a en/es/ko/pt...")
        translations = translate_query(query, target_languages=["en", "es", "ko", "pt"])
        print("\n📖 Traducciones generadas:")
        for lang, text in translations.items():
            if lang != "original":
                print(f"   [{lang}] {text}")
        print()

    # ─── Búsqueda con Playwright ──────────────────────────────────────────────
    all_results = []

    async with get_browser(headless=headless) as (browser, context):
        all_results = await search_all_sites(
            context=context,
            sites=sites,
            query_translations=translations,
            max_links_per_site=args.max_links,
        )

    # ─── Exportación ──────────────────────────────────────────────────────────
    print_summary(all_results, all_sites)

    if not all_results:
        print("⚠️  No se encontraron resultados. Revisa los logs en logs/")
        print(
            "   Tip: Intenta con --headless false para ver qué pasa en el navegador.\n"
            "   Tip: Revisa/actualiza los selectores CSS en config/sites.json.\n"
        )
        return

    if args.format == "xlsx":
        output_path = export_to_excel(
            results=all_results,
            query=query,
            output_dir=args.output_dir,
            sites=all_sites,
        )
    else:
        output_path = export_to_csv(
            results=all_results,
            query=query,
            output_dir=args.output_dir,
        )

    if output_path:
        print(f"\n✅ Resultados guardados en: {output_path}\n")
    else:
        print("\n❌ Error al guardar el archivo de resultados.\n")


if __name__ == "__main__":
    asyncio.run(main())
