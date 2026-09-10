# Contenedor del shell unificado (main.py + las 6 apps Streamlit).
# formulario-banda-900 y webscraping-internacional se despliegan como
# servicios separados (ver render.yaml) y se embeben vía iframe.
FROM python:3.11-slim

WORKDIR /app

COPY requirements_shell.txt ./
RUN pip install --no-cache-dir -r requirements_shell.txt

COPY main.py ./
COPY shell/ ./shell/
COPY pages_unificadas/ ./pages_unificadas/
COPY analisis-comentarios/ ./analisis-comentarios/
COPY chatbot-pqrs/ ./chatbot-pqrs/
COPY hoja-ruta/ ./hoja-ruta/
COPY observatorio-espectro/ ./observatorio-espectro/
COPY separacion-informacion/ ./separacion-informacion/
COPY vigilancia-tecnologica/ ./vigilancia-tecnologica/

ENV PORT=8501
EXPOSE 8501

CMD ["sh", "-c", "streamlit run main.py --server.address=0.0.0.0 --server.port=${PORT} --server.headless=true"]
