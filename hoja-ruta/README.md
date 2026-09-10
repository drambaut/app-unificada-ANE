# hoja-ruta---ANE

Dashboard y pipeline para responder una pregunta concreta:

```text
Que proyectos cubren cada una de las 29 actividades de la Hoja de Ruta SGP?
```

El sistema no evalua avance, ejecucion, confianza, evidencia documental ni decision de vigencia. Solo hace un mapeo semantico entre el contenido descriptivo de los proyectos y cada actividad.

## Arquitectura

- Gemini se ejecuta solo desde scripts de consola.
- Streamlit solo visualiza CSV procesados.
- El dashboard nunca llama Gemini.
- Python valida, consolida y calcula la cobertura global.

## Categorias de relacion

Cada par proyecto-actividad recibe exactamente uno de estos estados:

- `Cubre`: el objetivo, alcance o descripcion del proyecto coincide de manera clara y sustancial con la actividad.
- `Cubre parcialmente`: el proyecto atiende solo una parte o un componente de la actividad.
- `No cubre`: no hay relacion suficiente entre el proyecto y la actividad.

No existe `Por validar`, no se usa confianza y no se usa evidencia como criterio de degradacion.

## Como se realiza el cruce

1. `scripts/extract_roadmap_llm.py` extrae la tabla maestra de 29 actividades desde el PDF.
2. `scripts/map_projects_llm.py` compara cada actividad contra todos los proyectos.
3. Para 14 proyectos, el resultado esperado es `14 x 29 = 406` pares.
4. Gemini produce una clasificacion y una justificacion corta por par.
5. Python valida que no falte ningun par, que no haya duplicados y que los estados sean validos.
6. Python consolida la cobertura por actividad.

## Archivos de entrada

```text
data/raw/proyectos__raw.csv
data/raw/Estrategia de gestion de datos SGP_VF.pdf
```

## Archivos de salida

### Tabla maestra

```text
data/processed/hoja_ruta.csv
```

```csv
id_actividad,linea_hoja_ruta,actividad,horizonte,observaciones
```

Debe contener exactamente 29 actividades.

### Mapeo completo proyecto-actividad

```text
data/processed/mapeo_generado.csv
```

```csv
codigo_proyecto,nombre_proyecto,id_actividad,linea_hoja_ruta,actividad,estado_relacion,justificacion
```

Debe contener una fila por cada combinacion `codigo_proyecto + id_actividad`.

### Cobertura consolidada

```text
data/processed/cobertura_actividades.csv
```

```csv
id_actividad,linea_hoja_ruta,actividad,total_proyectos_que_cubren,total_proyectos_parciales,proyectos_que_cubren,proyectos_parciales,estado_cobertura
```

Estados consolidados:

- `Cubierta`: al menos un proyecto tiene `Cubre`.
- `Parcialmente cubierta`: ningun proyecto tiene `Cubre`, pero al menos uno tiene `Cubre parcialmente`.
- `Sin cobertura`: todos los proyectos tienen `No cubre`.

## Formula de cobertura

```text
porcentaje_cobertura =
(actividades_cubiertas + 0.5 * actividades_parcialmente_cubiertas)
/ 29 * 100
```

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuracion Gemini

Crea `.env`:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

Listar modelos:

```bash
python scripts/list_gemini_models.py
```

## Ejecutar pipeline

```bash
python scripts/run_pipeline.py
```

## Ejecutar dashboard

```bash
streamlit run app.py
```

La matriz principal usa proyectos como filas y las 29 actividades como columnas. La primera columna queda fija, la matriz permite scroll horizontal y cada celda incluye tooltip con proyecto, actividad, resultado y razon.

## Pruebas

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Las pruebas verifican que:

- La hoja de ruta tenga 29 actividades.
- El mapeo tenga `proyectos x 29` filas.
- No existan pares duplicados ni faltantes.
- Solo existan `Cubre`, `Cubre parcialmente` y `No cubre`.
- No aparezcan columnas de confianza, evidencia ni validacion.
- La consolidacion se haga en Python.
- La matriz use proyectos como filas y 29 actividades como columnas.
- El dashboard no llame Gemini.
- Un CSV valido no se reemplace si una nueva salida invalida falla validacion.


## Alcance

El dashboard muestra alineacion frente al plan. No mide avance tecnico, no tiene login, no permite edicion manual y no carga archivos desde la interfaz.
## Render

Render debe ejecutar solo:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

No se debe ejecutar Gemini automaticamente al abrir la app.

## Politica de datos

No subir a GitHub:

- `.env`
- claves o secretos
- PDF institucional original
- CSV crudos de proyectos
- logs
- respuestas crudas del LLM
- archivos temporales
- cache de Streamlit
- `__pycache__`
- entornos virtuales

Si un archivo sensible ya esta rastreado por Git, retiralo del seguimiento sin borrarlo localmente:

```bash
git rm --cached ruta/del/archivo
```
