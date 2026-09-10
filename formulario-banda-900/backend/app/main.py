import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import carga_masiva, config, estaciones, solicitudes
from .supabase_client import ensure_bucket_cargas

app = FastAPI(title="ANE - Solicitudes banda 900 MHz")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(solicitudes.router)
app.include_router(estaciones.router)
app.include_router(carga_masiva.router)
app.include_router(config.router)


@app.on_event("startup")
def on_startup():
    ensure_bucket_cargas()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Sirve el build de React (frontend/dist copiado aqui como "static" durante el
# build de Docker). Se registra al final para no tapar las rutas /api/*.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(STATIC_DIR):
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """
        Fallback estilo SPA: si el archivo existe en el build (ej. favicon.ico)
        se sirve tal cual; para cualquier otra ruta del frontend (/, /admin,
        /solicitud/5/reporte, etc.) se devuelve siempre index.html para que
        React Router la resuelva del lado del cliente. Sin esto, abrir esas
        rutas directamente (o recargar la pagina) daria 404 en produccion.
        """
        # index.html nunca se cachea: es lo que le dice al navegador qué
        # archivos JS/CSS (con hash) cargar. Sin esto, un navegador puede
        # quedarse sirviendo una versión vieja de index.html desde caché y
        # nunca enterarse de que hay assets nuevos, incluso con hard refresh
        # (esto pasa especialmente dentro de iframes).
        no_cache_headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        candidato = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidato):
            return FileResponse(candidato)
        return FileResponse(
            os.path.join(STATIC_DIR, "index.html"),
            headers=no_cache_headers,
        )