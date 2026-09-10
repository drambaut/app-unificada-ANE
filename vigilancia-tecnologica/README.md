# Vigilancia tecnológica del espectro radioeléctrico — MVP

## Descripción del MVP

Aplicación en Python para construir y explorar un corpus documental relacionado
con la gestión, el uso y la vigilancia del espectro radioeléctrico. El MVP
extrae texto de PDF y Excel, diagnostica el corpus, genera información
estructurada mediante un LLM, analiza tendencias y presenta resultados en un
dashboard Streamlit.

## Objetivo institucional

Apoyar la identificación temprana de tendencias regulatorias y tecnológicas,
bandas de frecuencia, actores y señales emergentes que puedan resultar
relevantes para la planeación y la agenda de la Agencia Nacional del Espectro
(ANE).

## Estructura del proyecto

```text
vigilancia-tecnologica---MVP/
├── app/                    # Extracción, análisis y dashboard
├── notebooks/              # Análisis exploratorio
├── outputs/                # Resultados locales; Git solo conserva .gitkeep
│   ├── extracted_text/
│   ├── structured_data/
│   ├── figures/
│   └── logs/
├── prompts/                # Instrucciones para extracción LLM
├── tests/                  # Pruebas automatizadas
├── .env.example            # Plantilla segura de configuración
├── requirements.txt
└── run_pipeline.py
```

## Datos reales no incluidos

Los PDF, Excel y demás documentos reales no forman parte de este repositorio.
La carpeta `Vigilanciatecnologica_data` debe permanecer fuera del repo. Los
resultados generados dentro de `outputs/` también están excluidos de Git.

## Estructura esperada de datos externos

```text
Herramienta_vigilancia_tecnologica/
├── Vigilanciatecnologica_data/
│   ├── CRC/
│   ├── Cullen International/
│   ├── ejercicio preliminar/
│   ├── GSMA/
│   ├── NERA/
│   ├── PolicyTracker/
│   ├── Reguladores/
│   └── WorldBank/
│
└── vigilancia-tecnologica---MVP/
```

La variable `DATA_DIR` referencia esa carpeta mediante una ruta relativa.

## Requisitos previos

- Python 3.10 o superior.
- PowerShell en Windows.
- Una clave de Google AI Studio solo para la fase opcional con Gemini.

## Preparación del entorno en Windows

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración del archivo `.env`

Crea la configuración local a partir de la plantilla:

```powershell
Copy-Item .env.example .env
```

Contenido esperado:

```dotenv
DATA_DIR=../Vigilanciatecnologica_data
OUTPUT_DIR=outputs

LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MAX_OUTPUT_TOKENS=65536

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Completa únicamente la clave del proveedor que vayas a usar. `.env` está
ignorado por Git y nunca debe publicarse.

### Configuración de Supabase

La arquitectura escalable usa Supabase para PostgreSQL y Storage. En local se
configura desde `.env` con estas variables:

```dotenv
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=source-documents
DASHBOARD_DATA_SOURCE=auto
```

`SUPABASE_KEY` debe ser una llave publica o anonima para lectura del dashboard.
Para la entrega actual, el dashboard publico puede ofrecer carga temporal de
documentos; esa carga debe ejecutarse del lado servidor con
`SUPABASE_SERVICE_ROLE_KEY` como variable de entorno de Render. Esa llave no
debe exponerse en navegador, logs publicos ni commits.

`GEMINI_MAX_OUTPUT_TOKENS` controla el tamaño máximo de las respuestas JSON de
Gemini. Para documentos institucionales grandes como PMGE/Agenda se recomienda
mantenerlo alto para evitar JSON truncado.

La autenticacion de usuarios, roles y permisos por perfil queda fuera de alcance
para esta entrega. El modo actual prioriza dashboard publico, documentos
precargados y carga temporal abierta para pruebas.

### Analisis transversal con Supabase

Cuando ya existan documentos `processed` en PostgreSQL, el flujo transversal se
ejecuta con:

```powershell
python run_supabase_transversal.py
```

El script construye el snapshot inmutable, ejecuta las tres etapas transversales
con Gemini, aplica el scoring matematico y publica la ejecucion solo si todo
termina correctamente. Requiere `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`GEMINI_API_KEY` y corpus procesado en Supabase.

Para publicar una version de dashboard con corpus creciente sin enviar un
contexto demasiado grande a Gemini, usa contexto acotado. Este modo mantiene
analisis real, pero prioriza sintesis y respuestas JSON pequenas:

```powershell
python run_supabase_transversal.py --bounded-context
```

Si una corrida anterior quedo activa despues de un corte o JSON invalido de
Gemini, reintenta esa misma ejecucion sin crear otra:

```powershell
python run_supabase_transversal.py --bounded-context --retry-active
```

Si el cupo de Gemini se agota cuando ya existen etapas transversales previas,
puedes publicar sin inventar evaluacion estrategica:

```powershell
python run_supabase_transversal.py --bounded-context --retry-run RUN_ID --empty-strategic-assessment
```

Para que Streamlit lea la publicacion vigente desde Supabase en vez de
`demo_data`, usa:

```dotenv
DASHBOARD_DATA_SOURCE=supabase
```

Con `DASHBOARD_DATA_SOURCE=auto`, Streamlit usa Supabase si `SUPABASE_URL` y
`SUPABASE_KEY` estan configuradas; si no, cae al modo demo para no romper la
vista publicada actual.

En modo Supabase, el dashboard muestra una carga publica temporal en la barra
lateral. Acepta PDF, XLS y XLSX, pide tipo de fuente y proveedor, procesa en
modo smoke por defecto y guarda el resultado en Supabase. Para que un documento
cargado aparezca en la publicacion vigente, ejecuta despues un nuevo analisis
transversal.

### Carga y procesamiento de corpus inicial

Para cargar documentos reales a Supabase Storage, analizarlos con Gemini y
persistirlos en PostgreSQL:

```powershell
python run_manual_processing.py ruta\al\corpus --source-type surveillance --recursive
```

Tipos soportados para `--source-type`: `surveillance`, `institutional_plan` y
`policy_matrix`. Antes de consumir Gemini puedes validar el lote con:

```powershell
python run_manual_processing.py ruta\al\corpus --source-type surveillance --recursive --dry-run
```

Para pruebas tecnicas pequenas puedes agregar `--metadata smoke=true`. En ese
modo Gemini devuelve una muestra acotada y valida para probar Storage,
PostgreSQL, validacion, persistencia y dashboard sin extraer todo el documento.

Para corpus grande, primero genera un manifiesto por lotes:

```powershell
python build_corpus_manifest.py "Vigilanciatecnologica_data\Vigilancia tecnológica" --batch-size 25 --output outputs\corpus_processing_manifest.csv
```

El manifiesto incluye `path`, `source_type`, `provider`, `priority`, `batch_id`,
`status` y `notes`. Solo incluye formatos soportados hoy por el pipeline:
PDF, XLS y XLSX.

Antes de consumir Gemini, revisa un lote:

```powershell
python run_corpus_manifest_batch.py outputs\corpus_processing_manifest.csv --batch-id batch-001 --dry-run
```

Para procesarlo con Supabase usando las llaves locales:

```powershell
.\scripts\run_corpus_manifest_batch_with_supabase_env.cmd outputs\corpus_processing_manifest.csv --batch-id batch-001 --skip-existing --report-csv outputs\corpus_batch-001_report.csv
```

Para pilotos tecnicos o lotes exploratorios, agrega `--smoke` para pedirle a
Gemini una extraccion acotada:

```powershell
.\scripts\run_corpus_manifest_batch_with_supabase_env.cmd outputs\corpus_processing_manifest.csv --batch-id batch-001 --limit 10 --smoke --skip-existing --report-csv outputs\corpus_batch-001_pilot_report.csv
```

Si un documento queda `failed`, reintenta solo fallidos con:

```powershell
.\scripts\run_corpus_manifest_batch_with_supabase_env.cmd outputs\corpus_processing_manifest.csv --batch-id batch-001 --limit 10 --smoke --reset-failed --skip-existing --report-csv outputs\corpus_batch-001_retry_report.csv
```

### Smoke check Supabase

Antes y despues de procesar corpus puedes revisar el estado operativo con:

```powershell
python run_supabase_healthcheck.py
```

Cuando ya esperes tener corpus procesado y publicacion vigente, usa:

```powershell
python run_supabase_healthcheck.py --strict
```

## Flujo del MVP

```text
Documentos PDF/Excel
→ extracción de texto
→ dataset base document_texts.csv
→ diagnóstico del corpus
→ extracción estructurada con LLM
→ análisis de tendencias
→ dashboard Streamlit
```

## Ejecución del pipeline de extracción y diagnóstico

```powershell
python run_pipeline.py
```

Este comando construye `document_texts.csv` y genera el diagnóstico inicial del
corpus. No ejecuta la fase LLM.

## Extracción estructurada con Gemini

Configura `GEMINI_API_KEY` en `.env` y ejecuta:

```powershell
python app/llm_extract.py
```

Por defecto se procesan 20 documentos y hasta 12.000 caracteres por documento.
Para modificar esos límites:

```powershell
python app/llm_extract.py --limit 50 --max-chars 12000
```

Esta fase puede consumir cuota o generar costos en el proveedor configurado.

## Procesamiento incremental con Gemini

La extracción puede limitarse a una cantidad de documentos, continuar desde
los resultados correctos existentes o regenerarse explícitamente:

```powershell
python app/llm_extract.py --limit 20
python app/llm_extract.py --limit 50 --resume
python app/llm_extract.py --limit 100 --resume
python app/llm_extract.py --limit all --resume
python app/llm_extract.py --limit all --overwrite
```

`--resume` procesa documentos pendientes y conserva el consolidado anterior.
`--overwrite` inicia desde cero. Sin ninguna de estas opciones, un archivo
`structured_documents.csv` existente no se sobrescribe.

Después de ampliar el conjunto procesado, actualice los archivos publicables:

```powershell
python app/dashboard_data_builder.py
```

Esto regenera los CSV analíticos y actualiza `demo_data/`.

## Análisis de resultados LLM

Después de generar `structured_documents.csv`:

```powershell
python app/llm_analysis.py
```

El análisis es local y no realiza llamadas adicionales al LLM.

## Dashboard Streamlit

```powershell
streamlit run app/dashboard.py
```

El dashboard presenta métricas, filtros, tendencias, detalle documental y los
reportes Markdown. Si falta algún resultado, muestra una advertencia sin
interrumpir las demás secciones.

## Modo demo con demo_data

El pipeline se ejecuta localmente. Después de generar
`outputs/structured_data/structured_documents.csv`, la capa analítica se crea con:

```powershell
python app/dashboard_data_builder.py
```

Los CSV limpios y agregados para publicación se copian a `demo_data/`. Render
leerá esta carpeta versionable sin depender de los PDF originales, textos
extraídos, Gemini ni una base de datos durante la demo. No se suben documentos
originales, archivos intermedios, logs ni claves API. La conexión a Supabase
queda aplazada para una fase posterior.

> Mejora futura: conexión a Supabase u otra base de datos para persistencia y
> actualización dinámica del dashboard.

## Dashboard rediseñado

El dashboard ejecutivo lee exclusivamente los archivos procesados de
demostración incluidos en `demo_data/`. Se inicia con:

```powershell
streamlit run app/dashboard.py
```

Para actualizar la publicación, ejecute localmente
`python app/dashboard_data_builder.py` y luego haga commit de los CSV renovados
en `demo_data/`. El dashboard publicado no requiere los documentos originales,
las salidas locales del pipeline, claves API ni una base de datos.

## Archivos generados localmente

Los principales resultados locales se guardan en:

- `outputs/structured_data/document_texts.csv`
- `outputs/structured_data/corpus_report.md`
- `outputs/structured_data/structured_documents.csv`
- `outputs/structured_data/llm_analysis_report.md`
- `outputs/structured_data/llm_*.csv`
- `outputs/extracted_text/`
- `outputs/figures/`
- `outputs/logs/`

Estos archivos no se versionan y pueden regenerarse ejecutando las fases.

## Estado actual

- Extracción de texto implementada.
- Diagnóstico del corpus implementado.
- Extracción estructurada con Gemini implementada.
- Análisis de resultados LLM implementado.
- Dashboard Streamlit implementado.
- El procesamiento LLM no se ejecuta automáticamente desde `run_pipeline.py`
  para evitar consumo accidental de API.

## Pruebas

```powershell
pytest
```

## Seguridad y datos sensibles

- No publiques `.env`, claves API, tokens ni credenciales.
- No copies claves reales dentro de `.env.example`, README, notebooks o código.
- No incorpores documentos reales ni resultados generados al repositorio.
- Revisa `repo_checklist.md` antes de cada publicación.

## Fases implementadas

1. Configuración y estructura del proyecto.
2. Extracción de texto desde PDF y Excel.
3. Diagnóstico exploratorio del corpus.
4. Extracción estructurada mediante Gemini u OpenAI.
5. Análisis local de resultados estructurados.
6. Dashboard Streamlit.

## Próximos pasos

- Ampliar la extracción LLM al corpus priorizado.
- Incorporar OCR para documentos escaneados.
- Añadir deduplicación y normalización semántica avanzada.
- Evaluar embeddings y búsqueda semántica.
- Agregar pruebas de calidad sobre extracciones y tendencias.
