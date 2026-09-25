import os
import sys
from pathlib import Path

import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[1] / "webscraping-internacional"
PORT = 8902

# Interruptor TEMPORAL de migración: con WEBSCRAPING_MODE=streamlit se ejecuta
# la nueva interfaz Streamlit (streamlit_app.py) dentro de este mismo proceso;
# con cualquier otro valor (o sin definir) se mantiene FastAPI + iframe.
# Se eliminará junto con el iframe cuando la versión Streamlit esté validada
# en el contenedor.
if os.getenv("WEBSCRAPING_MODE") == "streamlit":
    from shell.module_loader import run_isolated_from_path

    # streamlit_app.py agrega src/ a sys.path para importar search_jobs y sus
    # módulos planos (browser, scraper, ...). Se retira al terminar: esos
    # módulos ya quedan en sys.modules (no se purgan), así que JOBS y el hilo
    # de scraping siguen funcionando entre reruns.
    try:
        run_isolated_from_path(
            APP_ROOT / "streamlit_app.py",
            module_name="webscraping_ui",
            entry_func="main",
        )
    finally:
        src_dir_str = str(APP_ROOT / "src")
        while src_dir_str in sys.path:
            sys.path.remove(src_dir_str)
else:
    from shell.process_manager import ensure_running

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
