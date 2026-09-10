# App Unificada — ANE

Un solo shell de Streamlit que reúne las 8 herramientas de la ANE. Seis
corren dentro del mismo proceso Streamlit (misma navegación, misma sesión);
dos (formulario-banda-900 y webscraping-internacional) corren como
subprocesos FastAPI locales y se muestran embebidas dentro de la app vía
iframe.

## Puesta en marcha

1. Crea un entorno virtual e instala las dependencias combinadas:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements_unificado.txt
   playwright install chromium  # requerido por webscraping-internacional
   ```

2. Copia `.env.example` a `.env` en la raíz y completa las claves (Gemini,
   Supabase, etc.). Algunas sub-apps además leen su propio `.env` desde su
   propia carpeta (`hoja-ruta/.env`, `observatorio-espectro/.env`,
   `vigilancia-tecnologica/.env`, `formulario-banda-900/backend/app/.env`) —
   copia ahí las claves que correspondan hasta que se centralice la carga de
   configuración.

3. Compila el frontend de `formulario-banda-900` una sola vez:

   ```bash
   cd formulario-banda-900/frontend
   npm install
   npm run build
   xcopy /E /I dist ..\backend\static
   cd ../..
   ```

4. Arranca la app unificada desde la raíz:

   ```bash
   streamlit run main.py
   ```

Las 8 herramientas aparecen agrupadas en la barra de navegación lateral:
"IA generativa", "Datos y reportes" y "Formularios y scraping".

## Notas técnicas

- `shell/module_loader.py` aísla los paquetes `app`/`src` que varias
  sub-apps reutilizan con el mismo nombre, purgando `sys.modules` antes de
  cada carga de página.
- `shell/process_manager.py` lanza y reutiliza los subprocesos `uvicorn` de
  `formulario-banda-900` (puerto 8901) y `webscraping-internacional`
  (puerto 8902), embebidos vía `st.components.v1.iframe`.
- `st.set_page_config()` se llama una única vez, en `main.py`. Las 6 apps
  Streamlit originales tenían su propia llamada; se removió al integrarlas.
