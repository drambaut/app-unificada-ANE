# Contenedor del shell unificado (main.py + las apps Streamlit).
# formulario-banda-900 y webscraping-internacional se despliegan además como
# servicios separados (ver render.yaml) y se embeben vía iframe, salvo con
# BANDA900_MODE=streamlit / WEBSCRAPING_MODE=streamlit, que los ejecutan dentro
# de este contenedor (por eso incluye Playwright + Chromium).
FROM python:3.11-slim

WORKDIR /app

# Ruta fija para los navegadores de Playwright (no depende de $HOME).
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements_shell.txt ./
RUN pip install --no-cache-dir -r requirements_shell.txt

# Solo Chromium + sus dependencias de sistema (apt), instalados por la misma
# versión de Playwright que quedó en requirements_shell.txt, así el navegador
# y la librería siempre coinciden.
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY main.py ./
COPY shell/ ./shell/
COPY pages_unificadas/ ./pages_unificadas/
COPY analisis-comentarios/ ./analisis-comentarios/
COPY chatbot-pqrs/ ./chatbot-pqrs/
COPY hoja-ruta/ ./hoja-ruta/
COPY observatorio-espectro/ ./observatorio-espectro/
COPY separacion-informacion/ ./separacion-informacion/
COPY vigilancia-tecnologica/ ./vigilancia-tecnologica/
# Web Searcher: solo lo que usa la interfaz Streamlit (streamlit_app.py, src/ y
# config/). El FastAPI antiguo no se copia: el modo legacy usa WEBSCRAPING_URL.
COPY webscraping-internacional/streamlit_app.py ./webscraping-internacional/
COPY webscraping-internacional/src/ ./webscraping-internacional/src/
COPY webscraping-internacional/config/ ./webscraping-internacional/config/
# Banda 900: interfaz Streamlit + módulos de backend/app que usa (sin FastAPI,
# routers, React/Node ni build). El modo legacy usa FORMULARIO_B900_URL.
COPY formulario-banda-900/streamlit_app.py ./formulario-banda-900/
COPY formulario-banda-900/backend/app/__init__.py \
     formulario-banda-900/backend/app/settings.py \
     formulario-banda-900/backend/app/database.py \
     formulario-banda-900/backend/app/models.py \
     formulario-banda-900/backend/app/schemas.py \
     formulario-banda-900/backend/app/campos_antena.py \
     formulario-banda-900/backend/app/services.py \
     formulario-banda-900/backend/app/supabase_client.py \
     formulario-banda-900/backend/app/supabase_auth.py \
     formulario-banda-900/backend/app/divipola.json \
     ./formulario-banda-900/backend/app/

ENV PORT=8501
EXPOSE 8501

CMD ["sh", "-c", "streamlit run main.py --server.address=0.0.0.0 --server.port=${PORT} --server.headless=true"]
