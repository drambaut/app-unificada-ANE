# 🔍 Web Searcher

**Búsqueda automatizada en reguladores internacionales de telecomunicaciones**  
Desarrollado para la **Agencia Nacional del Espectro (ANE) · Colombia**

---

## ¿Qué hace?

Web Searcher es una herramienta web que busca automáticamente un tema en los sitios oficiales de los 10 principales organismos reguladores de telecomunicaciones del mundo, usando un navegador real (Chromium) para simular un usuario humano. Los resultados se pueden descargar en **Excel** o **CSV**.

El progreso se muestra en tiempo real: una tarjeta por organismo que pasa de *esperando* → *buscando* → *completado*, junto con un log detallado de cada acción.

---

## Organismos cubiertos

| ID | Organismo | País / Región | Idioma de búsqueda |
|---|---|---|---|
| `ITU` | Unión Internacional de Telecomunicaciones | Internacional | Español |
| `CEPT` | Conferencia Europea de Adm. de Correos y Telecomunicaciones | Europa / Región 1 | Inglés |
| `ISED` | Ministerio de Innovación, Ciencia y Desarrollo Económico | Canadá / Región 2 | Inglés |
| `FCC` | Comisión Federal de Comunicaciones | EE.UU. / Región 2 | Inglés |
| `OFCOM` | Oficina de Comunicaciones | Reino Unido / Región 1 | Inglés |
| `CRT` | Comisión Reguladora de Telecomunicaciones | México / Región 2 | Español |
| `ANATEL` | Agencia Nacional de Telecomunicaciones | Brasil / Región 2 | Portugués |
| `SUBTEL` | Subsecretaría de Telecomunicaciones | Chile / Región 2 | Español |
| `ACMA` | Autoridad de Comunicaciones y Medios Australiana | Australia / Región 3 | Inglés |
| `MSIT` | Ministerio de Ciencia y TIC | Corea del Sur / Región 3 | Coreano |

> La traducción automática convierte tu búsqueda al idioma de cada sitio usando Google Translate (sin API key).

---

## Arquitectura

```
webscraping-temas-internacionales---ANE/
│
├── main_api.py          ← Backend FastAPI (API REST + Server-Sent Events)
│
├── static/
│   └── index.html       ← Frontend completo (HTML + CSS + JS, archivo único)
│
├── src/
│   ├── browser.py       ← Gestión de Playwright / Chromium (anti-detección)
│   ├── scraper.py       ← Lógica de búsqueda y extracción de links
│   ├── translator.py    ← Traducción automática con deep_translator
│   └── exporter.py      ← Exportación a Excel (.xlsx) y CSV
│
├── config/
│   └── sites.json       ← Configuración de los 10 organismos (URLs, selectores CSS)
│
├── requirements.txt
├── render.yaml          ← Despliegue automático en Render
└── README.md
```

### Flujo de datos

```
Usuario escribe query
        │
        ▼
POST /api/search  →  Traduce query (en/es/ko/pt)
        │             Crea Job con ID único
        │             Lanza hilo de scraping
        ▼
GET /api/progress/{job_id}  ←─── Server-Sent Events (SSE)
        │                          El frontend recibe eventos en tiempo real:
        │                          progreso, logs, conteo de links por sitio
        ▼
GET /api/download/{job_id}  →  Descarga Excel o CSV
```

---

## Instalación local

### Requisitos previos

- Python 3.9 o superior
- pip actualizado: `python -m pip install --upgrade pip`

### Pasos

```bash
# 1. Clonar o descargar el repositorio
git clone https://github.com/drambaut/webscraping-temas-internacionales---ANE.git
cd web-searcher

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Instalar el navegador Chromium de Playwright (solo una vez, ~150 MB)
playwright install chromium

# 4. Iniciar el servidor
uvicorn app:app --reload --port 8000
```

Abre el navegador en **http://localhost:8000**

---

## Uso

### Búsqueda básica

1. Escribe el tema a buscar en la barra principal (en cualquier idioma).
2. Haz clic en **Buscar**.
3. Espera mientras el sistema visita cada organismo uno a uno.
4. Al terminar, descarga el archivo Excel con todos los links encontrados.

### Opciones avanzadas

Haz clic en **Opciones de búsqueda** para:

| Opción | Descripción |
|---|---|
| **Organismos a consultar** | Selecciona uno, varios o todos |
| **Formato de descarga** | Excel `.xlsx` (por defecto) o CSV `.csv` |
| **Traducción automática** | Activa/desactiva la traducción al idioma de cada sitio |

### Archivo de resultados

El Excel generado incluye dos hojas:

- **Resultados** — todos los links con columnas: Organismo, Nombre, Query usada, Idioma, URL (con hipervínculo), Texto del link, Fecha/Hora.
- **Resumen** — conteo de links por organismo con indicador verde/rojo.

---

## Despliegue en Render

El repositorio incluye `render.yaml` con toda la configuración lista.

### Pasos

1. Sube el proyecto a un repositorio **GitHub** (público o privado).
2. Entra a [render.com](https://render.com) → **New Web Service**.
3. Conecta el repositorio.
4. Render detecta el `render.yaml` automáticamente.
5. Haz clic en **Deploy**.

### Variables de entorno (ya configuradas en `render.yaml`)

| Variable | Valor |
|---|---|
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/render/.cache/ms-playwright` |
| `PYTHONUNBUFFERED` | `1` |

### Plan recomendado

| Plan | RAM | ¿Suficiente? |
|---|---|---|
| Starter | 512 MB | ⚠️ Justo para Chromium |
| **Standard** | **1 GB** | **✅ Recomendado** |
| Pro | 2 GB | ✅ Holgado |

> Chromium requiere al menos ~400 MB de RAM en ejecución. Se recomienda el plan **Standard**.

---

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Sirve la interfaz web (`index.html`) |
| `GET` | `/api/sites` | Lista de organismos configurados |
| `POST` | `/api/search` | Inicia una búsqueda, devuelve `job_id` |
| `GET` | `/api/progress/{job_id}` | Stream SSE con el progreso en tiempo real |
| `GET` | `/api/download/{job_id}` | Descarga el archivo de resultados |

### Ejemplo — `POST /api/search`

```json
{
  "query": "gestión del espectro radioeléctrico",
  "site_ids": ["itu", "fcc", "ofcom"],
  "no_translate": false,
  "format": "xlsx",
  "max_links": 50
}
```

---

## Personalizar organismos (`config/sites.json`)

Si un sitio no devuelve resultados, lo más probable es que su selector CSS haya cambiado.

### Campos configurables

```json
{
  "id": "fcc",
  "name": "Comisión Federal de Comunicaciones (FCC)",
  "url": "https://www.fcc.gov/",
  "language": "en",
  "region": "Región 2",
  "search_url": "https://www.fcc.gov/search/#q={query}",
  "search_method": "url",
  "result_links": ".searchresult a[href]",
  "result_link_filter": "fcc.gov",
  "wait_for": ".searchresult"
}
```

| Campo | Descripción |
|---|---|
| `search_url` | URL con `{query}` como marcador. Método preferido. |
| `search_method` | `"url"` (directo) o `"form"` (interacción con formulario) |
| `result_links` | Selector CSS de los links de resultados |
| `result_link_filter` | Filtra links que contengan este texto (ej: el dominio) |
| `wait_for` | Selector que indica que la página ya cargó los resultados |

### Cómo actualizar un selector

1. Abre el sitio en Chrome.
2. Clic derecho sobre un resultado de búsqueda → **Inspeccionar**.
3. Copia el selector CSS del elemento `<a>`.
4. Actualiza `result_links` en `config/sites.json`.

---

## Solución de problemas

### "No se encontraron resultados en ningún sitio"
- Verifica tu conexión a internet.
- El sitio pudo haber cambiado sus selectores CSS → actualiza `sites.json`.
- Algunos sitios bloquean bots agresivamente; los tiempos de espera en `browser.py` pueden necesitar ajuste.

### Error de memoria en Render
- Sube al plan **Standard** (1 GB RAM).

### `playwright install-deps` falla en el build
- Agrega un script `build.sh` que ejecute ambos comandos por separado con `set -e`.

### El log muestra "Error de timeout"
- Aumenta el `timeout` en `browser.py` → función `safe_goto()`.

---

## Dependencias principales

| Librería | Versión mínima | Uso |
|---|---|---|
| `fastapi` | 0.111.0 | Backend web y API REST |
| `uvicorn` | 0.30.0 | Servidor ASGI para producción |
| `playwright` | 1.44.0 | Automatización de Chromium |
| `deep-translator` | 1.11.4 | Traducción gratuita sin API key |
| `openpyxl` | 3.1.2 | Generación de archivos Excel |

---

## Uso mensual recomendado (flujo de trabajo ANE)

```
Cada mes:
  1. Abrir la herramienta en el navegador
  2. Escribir el tema del mes (ej: "asignación de espectro 5G")
  3. Seleccionar los organismos de interés (o dejar todos)
  4. Hacer clic en Buscar y esperar (~5-15 min según la cantidad de sitios)
  5. Descargar el Excel con los resultados
  6. Revisar los links en la hoja "Resultados"
```

---

## Licencia

Herramienta de uso interno — Agencia Nacional del Espectro, Colombia.  
Código abierto, sin restricciones de uso.