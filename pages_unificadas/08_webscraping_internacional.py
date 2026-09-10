import os
from pathlib import Path

import streamlit as st

from shell.process_manager import ensure_running

APP_ROOT = Path(__file__).resolve().parents[1] / "webscraping-internacional"
PORT = 8902

st.title("🌐 Web Searcher — Reguladores internacionales")

# En Render, este servicio corre como una app aparte (ver render.yaml) y no
# se puede alcanzar "localhost" del servidor desde el navegador del usuario.
# Por eso, si existe una URL pública configurada, se usa directamente.
public_url = os.getenv("WEBSCRAPING_URL")

if public_url:
    st.iframe(public_url, height=1600)
else:
    with st.spinner("Iniciando el motor de búsqueda (Playwright)..."):
        ok = ensure_running(
            name="webscraping-internacional",
            cwd=APP_ROOT,
            cmd=["uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT)],
            port=PORT,
            startup_timeout=25.0,
        )

    if not ok:
        st.error(
            "No fue posible iniciar Web Searcher. Verifica que las dependencias "
            "estén instaladas y que Chromium esté disponible para Playwright:\n\n"
            "```bash\npip install -r webscraping-internacional/requirements.txt\n"
            "playwright install chromium\n```"
        )
    else:
        st.iframe(f"http://127.0.0.1:{PORT}", height=1600)
