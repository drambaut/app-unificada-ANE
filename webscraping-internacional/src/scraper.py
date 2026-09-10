"""
scraper.py
==========
Lógica principal de búsqueda y extracción de links.
Soporta dos métodos:
  - 'url': Búsqueda directa via URL (más rápido y confiable).
  - 'form': Interacción con formulario real en la página (fallback).
"""

import logging
import re
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

from playwright.async_api import Page

from browser import (
    human_delay,
    safe_goto,
    find_element_multi,
    try_search_box,
)

logger = logging.getLogger("telecom_searcher.scraper")

# Links a ignorar (recursos, anclas, JS, redes sociales)
IGNORE_PATTERNS = [
    r"^#",
    r"^javascript:",
    r"^mailto:",
    r"^tel:",
    r"\.(jpg|jpeg|png|gif|svg|pdf|css|js|ico|woff|woff2|ttf)(\?.*)?$",
    r"facebook\.com",
    r"twitter\.com",
    r"instagram\.com",
    r"youtube\.com",
    r"linkedin\.com",
]


def is_valid_link(href: str, base_filter: str = "") -> bool:
    """
    Determina si un link es válido para incluirlo en resultados.

    Args:
        href: URL a evaluar.
        base_filter: Si se especifica, solo acepta links que contengan esta cadena.

    Returns:
        True si el link es válido.
    """
    if not href or len(href) < 5:
        return False

    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, href, re.IGNORECASE):
            return False

    # Si hay filtro de dominio, aplicarlo
    if base_filter and base_filter not in href:
        return False

    # Debe ser una URL absoluta o relativa válida
    return href.startswith(("http://", "https://", "/"))


def resolve_url(href: str, base_url: str) -> str:
    """Convierte un link relativo en URL absoluta."""
    if href.startswith(("http://", "https://")):
        return href
    return urllib.parse.urljoin(base_url, href)


async def extract_links(
    page: Page,
    site: dict,
    query: str,
    language: str,
) -> List[Dict]:
    results = []
    base_filter = site.get("result_link_filter", "")
    current_url = page.url

    try:
        # Esperar a que carguen los resultados
        wait_selector = site.get("wait_for", "")
        if wait_selector:
            for sel in [s.strip() for s in wait_selector.split(",")]:
                try:
                    await page.wait_for_selector(sel, timeout=10000)
                    logger.debug(f"wait_for satisfecho con: '{sel}'")
                    break
                except Exception:
                    continue

        # ── NUEVO: usar result_links del JSON si está definido ──────────────
        # Si el sitio tiene un selector específico (ej: "a.gs-title" para ITU),
        # úsalo en lugar del genérico "a[href]" que trae links de menú/footer.
        result_links_selector = site.get("result_links", "a[href]")
        if not result_links_selector or result_links_selector == "a[href]":
            result_links_selector = "a[href]"  # genérico como antes

        links_data = await page.evaluate(f"""
            () => {{
                const links = Array.from(document.querySelectorAll('{result_links_selector}'));
                return links.map(a => ({{
                    href: a.href,
                    text: (a.innerText || a.textContent || '').trim().substring(0, 200),
                    title: a.getAttribute('title') || '',
                }}));
            }}
        """)
        # ────────────────────────────────────────────────────────────────────

        seen = set()
        for link in links_data:
            href = link.get("href", "").strip()
            text = link.get("text", "").strip()
            title = link.get("title", "").strip()
            resolved = resolve_url(href, current_url)

            if not is_valid_link(resolved, base_filter):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)

            results.append({
                "site_id": site["id"],
                "site_name": site["name"],
                "query": query,
                "language": language,
                "url": resolved,
                "link_text": text or title or "Sin texto",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        logger.info(
            f"[{site['id']}] Query='{query}' ({language}): "
            f"{len(results)} links extraídos"
        )

    except Exception as e:
        logger.error(f"Error al extraer links de {site['name']}: {e}")

    return results
async def search_via_url(
    page: Page,
    site: dict,
    query: str,
    language: str,
) -> List[Dict]:
    """
    Realiza búsqueda construyendo la URL de búsqueda directamente.
    Método preferido: más rápido y menos propenso a bloqueos.
    """
    search_url_template = site.get("search_url", "")

    if not search_url_template:
        logger.warning(f"[{site['id']}] No tiene 'search_url' configurada.")
        return []

    encoded_query = urllib.parse.quote_plus(query)
    search_url = search_url_template.replace("{query}", encoded_query)

    logger.info(f"[{site['id']}] Búsqueda via URL: {search_url}")

    if not await safe_goto(page, search_url):
        return []

    await human_delay(2.0, 3.0)
    return await extract_links(page, site, query, language)


async def search_via_form(
    page: Page,
    site: dict,
    query: str,
    language: str,
) -> List[Dict]:
    """
    Realiza búsqueda interactuando con el formulario real de la página.
    Método fallback: simula lo que haría un usuario humano.
    """
    logger.info(f"[{site['id']}] Búsqueda via formulario en: {site['url']}")

    if not await safe_goto(page, site["url"]):
        return []

    await human_delay(1.5, 2.5)

    # Intentar con la barra de búsqueda
    success = await try_search_box(page, site, query)

    if not success:
        logger.warning(
            f"[{site['id']}] Fallo en formulario. "
            "Intenta actualizar los selectores CSS en config/sites.json"
        )
        return []

    return await extract_links(page, site, query, language)


async def search_site(
    page: Page,
    site: dict,
    query: str,
    language: str,
    force_form: bool = False,
) -> List[Dict]:
    """
    Orquesta la búsqueda en un sitio usando el método más apropiado.
    
    Estrategia:
    1. Si 'search_method' es 'url' o hay 'search_url', intenta búsqueda via URL.
    2. Si falla o el método es 'form', usa interacción con formulario.
    3. Si todo falla, retorna lista vacía con log de advertencia.

    Args:
        page: Página de Playwright.
        site: Config del sitio.
        query: Texto a buscar.
        language: Código de idioma de la query.
        force_form: Si True, fuerza el método de formulario.

    Returns:
        Lista de resultados encontrados (puede ser vacía si hay errores).
    """
    results = []
    method = site.get("search_method", "url")

    try:
        if not force_form and (method == "url" or site.get("search_url")):
            results = await search_via_url(page, site, query, language)

            # Si URL no dio resultados, intentar formulario como fallback
            if not results and site.get("search_box"):
                logger.info(
                    f"[{site['id']}] URL sin resultados, intentando formulario..."
                )
                results = await search_via_form(page, site, query, language)
        else:
            results = await search_via_form(page, site, query, language)

    except Exception as e:
        logger.error(f"[{site['id']}] Error inesperado al buscar '{query}': {e}")

    return results


async def search_all_sites(
    context,
    sites: List[dict],
    query_translations: Dict[str, str],
    max_links_per_site: int = 50,
) -> List[Dict]:
    """
    Ejecuta la búsqueda en todos los sitios configurados.

    Args:
        context: Contexto de Playwright (BrowserContext).
        sites: Lista de configuraciones de sitios.
        query_translations: Dict {idioma: query} generado por translator.py.
        max_links_per_site: Límite máximo de links por sitio por búsqueda.

    Returns:
        Lista combinada de todos los resultados de todos los sitios.
    """
    from translator import get_all_queries_for_site

    all_results = []
    total_sites = len(sites)

    for i, site in enumerate(sites, 1):
        logger.info(
            f"\n{'='*60}\n"
            f"[{i}/{total_sites}] Procesando: {site['name']}\n"
            f"{'='*60}"
        )

        # Obtener las queries a usar para este sitio (en su idioma + en y es)
        queries_to_try = get_all_queries_for_site(site, query_translations)

        # Crear una nueva página por sitio (aislamiento de cookies/sesión)
        page = await context.new_page()

        site_results = []

        for lang, query in queries_to_try:
            logger.info(f"  → Query [{lang}]: '{query}'")
            results = await search_site(page, site, query, lang)

            # Aplicar límite de links por búsqueda
            site_results.extend(results[:max_links_per_site])

            # Pausa entre búsquedas del mismo sitio
            await human_delay(1.5, 2.5)

        # Deduplicar resultados del mismo sitio
        seen_urls = set()
        unique_results = []
        for r in site_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)

        logger.info(
            f"[{site['id']}] Total único: {len(unique_results)} links encontrados"
        )
        all_results.extend(unique_results)

        await page.close()

        # Pausa entre sitios
        if i < total_sites:
            await human_delay(2.0, 4.0)

    return all_results
