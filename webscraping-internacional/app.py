"""
main_api.py — FastAPI backend para Web Searcher
========================================================
Ejecutar localmente:   uvicorn main_api:app --reload --port 8000
Producción (Render):   uvicorn main_api:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List

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

from search_jobs import JOBS, JobInputError, start_job

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
    try:
        started = start_job(
            query=req.query,
            site_ids=req.site_ids,
            no_translate=req.no_translate,
            fmt=req.format,
            max_links=req.max_links,
            all_sites=ALL_SITES,
        )
    except JobInputError as e:
        raise HTTPException(400, str(e))

    return {
        "job_id": started.job.id,
        "sites": [{"id": s["id"], "name": s["name"]} for s in started.sites],
        "translations": {k: v for k, v in started.translations.items()
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