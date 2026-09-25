import os
import sys
from pathlib import Path

import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[1] / "formulario-banda-900"
BACKEND_DIR = APP_ROOT / "backend"
PORT = 8901

# Interruptor TEMPORAL de migración: con BANDA900_MODE=streamlit se ejecuta la
# nueva interfaz Streamlit (streamlit_app.py) dentro de este mismo proceso; con
# cualquier otro valor (o sin definir) se mantiene FastAPI + React vía iframe.
# Se eliminará junto con el iframe cuando la versión Streamlit esté validada
# en el contenedor.
if os.getenv("BANDA900_MODE") == "streamlit":
    from shell.module_loader import run_isolated_from_path

    # streamlit_app.py agrega backend/ a sys.path para importar su paquete "app",
    # que comparte nombre con el de otras sub-apps. Al terminar se retiran la
    # ruta y esos módulos para no dejar nada de Banda en el proceso compartido
    # (run_isolated/run_isolated_from_path igual purgan "app" antes de cargar).
    try:
        run_isolated_from_path(
            APP_ROOT / "streamlit_app.py",
            module_name="banda900_ui",
            entry_func="main",
        )
    finally:
        backend_dir_str = str(BACKEND_DIR)
        while backend_dir_str in sys.path:
            sys.path.remove(backend_dir_str)
        for name in [n for n in sys.modules if n == "app" or n.startswith("app.")]:
            if str(getattr(sys.modules[name], "__file__", "") or "").startswith(backend_dir_str):
                del sys.modules[name]
else:
    from shell.process_manager import ensure_running

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
