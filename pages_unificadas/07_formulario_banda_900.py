import os
from pathlib import Path

import streamlit as st

from shell.process_manager import ensure_running

APP_ROOT = Path(__file__).resolve().parents[1] / "formulario-banda-900"
BACKEND_DIR = APP_ROOT / "backend"
PORT = 8901

st.title("📝 Formulario Banda 900")

# En Render, este servicio corre como una app aparte (ver render.yaml) y no
# se puede alcanzar "localhost" del servidor desde el navegador del usuario.
# Por eso, si existe una URL pública configurada, se usa directamente.
public_url = os.getenv("FORMULARIO_B900_URL")

if public_url:
    st.iframe(public_url, height=2400)
else:
    if not (BACKEND_DIR / "static" / "index.html").exists():
        st.error(
            "El frontend de esta app aún no está compilado.\n\n"
            "Ejecuta una sola vez, desde `formulario-banda-900/frontend/`:\n\n"
            "```bash\nnpm install\nnpm run build\n```\n\n"
            "y copia el contenido de `frontend/dist/` a `backend/static/` "
            "(el Dockerfile del proyecto hace exactamente esto)."
        )
        st.stop()

    with st.spinner("Iniciando el backend del formulario..."):
        ok = ensure_running(
            name="formulario-banda-900",
            cwd=BACKEND_DIR,
            cmd=["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            port=PORT,
        )

    if not ok:
        st.error(
            "No fue posible iniciar el backend del formulario. Verifica las variables "
            "de entorno de Supabase en el `.env` unificado y que el puerto "
            f"{PORT} esté libre."
        )
    else:
        st.iframe(f"http://127.0.0.1:{PORT}", height=2400)
