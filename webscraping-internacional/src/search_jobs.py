"""
search_jobs.py
==============
Ejecución y registro de trabajos de búsqueda (jobs), independiente de FastAPI.

Contiene el modelo Job, el registro en memoria JOBS y el motor que corre el
scraping en un hilo propio con su event loop. Lo usa app.py (FastAPI) y
puede usarlo cualquier otra interfaz que importe este módulo.

Uso:
    started = start_job(query, site_ids, no_translate, fmt, max_links, all_sites)
    job = JOBS[started.job.id]   # progreso: job.current, job.logs, job.status...
"""

import asyncio
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from browser    import get_browser, human_delay
from exporter   import export_to_csv, export_to_excel
from scraper    import search_site
from translator import get_all_queries_for_site, translate_query


class JobInputError(ValueError):
    """Parámetros inválidos al iniciar un job (query vacía, sin sitios válidos)."""


# ── Modelo de Job ─────────────────────────────────────────────────────────────
@dataclass
class Job:
    id: str
    status: str = "pending"            # pending | running | done | error
    current: int = 0
    total: int = 0
    current_site_id: str = ""
    current_site_name: str = ""
    logs: List[str] = field(default_factory=list)
    site_results: Dict[str, int] = field(default_factory=dict)
    results: List[Dict] = field(default_factory=list)
    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    file_mime: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")


JOBS: Dict[str, Job] = {}


def _cleanup_old_jobs():
    """Elimina jobs con más de 1 hora de antigüedad."""
    now = time.time()
    stale = [jid for jid, j in JOBS.items() if now - j.created_at > 3600]
    for jid in stale:
        del JOBS[jid]


# ── Motor de scraping (corre en hilo propio) ──────────────────────────────────
async def _run_scraper(job: Job, sites: list, translations: dict,
                       max_links: int, fmt: str, all_sites: list):
    job.status = "running"
    job.total  = len(sites)
    job.log(f"Iniciando búsqueda en {len(sites)} organismo(s)...")

    try:
        async with get_browser(headless=True) as (browser, context):
            for i, site in enumerate(sites, 1):
                job.current           = i - 1
                job.current_site_id   = site["id"]
                job.current_site_name = site["name"]
                job.log(f"[{i}/{job.total}] {site['name']}")

                queries     = get_all_queries_for_site(site, translations)
                page        = await context.new_page()
                site_buffer = []

                for lang, query in queries:
                    job.log(f"  → [{lang.upper()}] \"{query}\"")
                    try:
                        res = await search_site(page, site, query, lang)
                        site_buffer.extend(res[:max_links])
                        job.log(f"  ✓ {len(res)} links encontrados")
                    except Exception as e:
                        job.log(f"  ✗ {str(e)[:100]}")
                    await human_delay(1.0, 2.0)

                # Deduplicar URLs del sitio
                seen: set = set()
                unique = [r for r in site_buffer
                          if r["url"] not in seen and not seen.add(r["url"])]

                job.results.extend(unique)
                job.site_results[site["id"]] = len(unique)
                job.current = i
                job.log(f"  ━ {len(unique)} links únicos")

                await page.close()
                if i < len(sites):
                    await human_delay(1.5, 3.0)

        total = len(job.results)
        job.log("")
        job.log(f"✅ Completado — {total} links en total")

        # Generar archivo de exportación
        with tempfile.TemporaryDirectory() as tmpdir:
            q = translations.get("original", "search")
            if fmt == "xlsx":
                path = export_to_excel(job.results, q, tmpdir, all_sites)
                job.file_mime = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                path = export_to_csv(job.results, q, tmpdir)
                job.file_mime = "text/csv"

            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    job.file_bytes = f.read()
                job.file_name = Path(path).name

        job.status = "done"

    except Exception as e:
        job.error_msg = str(e)
        job.log(f"❌ Error fatal: {e}")
        job.status = "error"


def _thread_runner(job: Job, sites: list, translations: dict,
                   max_links: int, fmt: str, all_sites: list):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _run_scraper(job, sites, translations, max_links, fmt, all_sites)
        )
    finally:
        loop.close()


# ── Inicio de un job ──────────────────────────────────────────────────────────
@dataclass
class StartedJob:
    job: Job
    sites: list          # sitios que se van a consultar
    translations: dict   # incluye la clave "original"


def start_job(query: str, site_ids: List[str], no_translate: bool,
              fmt: str, max_links: int, all_sites: list) -> StartedJob:
    """
    Valida los parámetros, traduce la query, registra el job en JOBS y lanza
    el scraping en un hilo daemon. Retorna de inmediato.

    Args:
        query: Texto a buscar (se le aplica strip()).
        site_ids: IDs de sitios a consultar; lista vacía = todos.
        no_translate: Si True, usa la query original para todos los idiomas.
        fmt: "xlsx" o cualquier otro valor para CSV.
        max_links: Máx. links por búsqueda en cada sitio.
        all_sites: Configuración completa de sitios (sites.json).

    Raises:
        JobInputError: si la query está vacía o no hay sitios válidos.
    """
    _cleanup_old_jobs()

    query = query.strip()
    if not query:
        raise JobInputError("La query no puede estar vacía")

    sites = [s for s in all_sites
             if not site_ids or s["id"] in site_ids]
    if not sites:
        raise JobInputError("No se encontraron sitios válidos")

    # Traducciones
    if no_translate:
        translations = {
            "original": query,
            "en": query, "es": query, "ko": query, "pt": query,
        }
    else:
        translations = translate_query(query, ["en", "es", "ko", "pt"])
    translations["original"] = query

    # Crear job y lanzar hilo
    job_id = str(uuid.uuid4())[:8]
    job    = Job(id=job_id)
    JOBS[job_id] = job

    thread = threading.Thread(
        target=_thread_runner,
        args=(job, sites, translations, max_links, fmt, all_sites),
        daemon=True,
    )
    thread.start()

    return StartedJob(job=job, sites=sites, translations=translations)
