"""
main_api.py — FastAPI backend para Web Searcher
========================================================
Ejecutar localmente:   uvicorn main_api:app --reload --port 8000
Producción (Render):   uvicorn main_api:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
SRC_DIR     = BASE_DIR / "src"
STATIC_DIR  = BASE_DIR / "static"
CONFIG_PATH = BASE_DIR / "config" / "sites.json"

sys.path.insert(0, str(SRC_DIR))

from browser    import get_browser, human_delay
from exporter   import export_to_csv, export_to_excel
from scraper    import search_site
from translator import get_all_queries_for_site, translate_query

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Web Searcher — ANE")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Configuración ─────────────────────────────────────────────────────────────
def _load_sites() -> list:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

try:
    ALL_SITES: list = _load_sites()
except FileNotFoundError:
    ALL_SITES = []
    print(f"⚠️  ADVERTENCIA: No se encontró {CONFIG_PATH}")


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
                       max_links: int, fmt: str):
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
                path = export_to_excel(job.results, q, tmpdir, ALL_SITES)
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
                   max_links: int, fmt: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _run_scraper(job, sites, translations, max_links, fmt)
        )
    finally:
        loop.close()


# ── Rutas API ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=FileResponse)
async def root():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "index.html no encontrado en static/")
    return FileResponse(str(index))


@app.get("/api/sites")
async def get_sites():
    if not ALL_SITES:
        raise HTTPException(503, "Configuración de sitios no disponible")
    return ALL_SITES


class SearchRequest(BaseModel):
    query: str
    site_ids: List[str] = []
    no_translate: bool = False
    format: str = "xlsx"
    max_links: int = 50


@app.post("/api/search")
async def start_search(req: SearchRequest):
    _cleanup_old_jobs()

    query = req.query.strip()
    if not query:
        raise HTTPException(400, "La query no puede estar vacía")

    sites = [s for s in ALL_SITES
             if not req.site_ids or s["id"] in req.site_ids]
    if not sites:
        raise HTTPException(400, "No se encontraron sitios válidos")

    # Traducciones
    if req.no_translate:
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
        args=(job, sites, translations, req.max_links, req.format),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "sites": [{"id": s["id"], "name": s["name"]} for s in sites],
        "translations": {k: v for k, v in translations.items()
                         if k != "original"},
    }


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")

    async def _generate():
        last_log_idx = 0

        while True:
            job = JOBS.get(job_id)
            if not job:
                yield _sse({"type": "error", "msg": "Job no encontrado"})
                return

            # Enviar logs nuevos
            new_logs = job.logs[last_log_idx:]
            for msg in new_logs:
                yield _sse({"type": "log", "msg": msg})
            last_log_idx += len(new_logs)

            # Enviar estado de progreso
            yield _sse({
                "type":         "progress",
                "current":      job.current,
                "total":        job.total,
                "site_id":      job.current_site_id,
                "site_name":    job.current_site_name,
                "site_results": job.site_results,
            })

            if job.status == "done":
                yield _sse({
                    "type":         "done",
                    "total":        len(job.results),
                    "site_results": job.site_results,
                    "has_file":     job.file_bytes is not None,
                })
                return

            if job.status == "error":
                yield _sse({"type": "error", "msg": job.error_msg or "Error desconocido"})
                return

            await asyncio.sleep(0.4)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/download/{job_id}")
async def download_file(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    if job.status != "done" or not job.file_bytes:
        raise HTTPException(400, "Archivo no disponible aún")

    return Response(
        content=job.file_bytes,
        media_type=job.file_mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{job.file_name}"'
        },
    )


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)