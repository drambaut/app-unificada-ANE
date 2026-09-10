# Cruce de Estaciones Base — TIGO / TELECOMUNICACIONES

Aplicación en **Streamlit + Python** que cruza la información de estaciones
base reportada por **COLOMBIA MÓVIL S.A. E.S.P.** y **COLOMBIA
TELECOMUNICACIONES S.A. E.S.P.** y genera cuatro archivos Excel
descargables: `UT5.xlsx`, `UT.xlsx`, `CMO.xlsx` y `TEL.xlsx`.

## Qué hace la aplicación

1. El usuario carga dos archivos Excel (el nombre del archivo puede ser
   cualquiera, no se depende de un nombre exacto):
   - Archivo de **COLOMBIA MÓVIL S.A. E.S.P.**
   - Archivo de **COLOMBIA TELECOMUNICACIONES S.A. E.S.P.**
2. De cada archivo se procesa exclusivamente la hoja
   `PARAMET_TEC_SECTORES_ESTA_BASE`.
3. Se determina, para cada fila de cada archivo, si su estación es
   **compartida** con el otro operador (ver definición exacta abajo).
4. Según si la fila es compartida y el valor de
   `BANDA_FRECUENCIA_OPERAC_SECTOR`, cada fila se clasifica en uno de los
   cuatro archivos de salida.
5. Los cuatro archivos se pueden descargar individualmente o todos juntos
   en un ZIP.

## Definición exacta de estación compartida

Una fila de **COLOMBIA MÓVIL** se considera compartida con **COLOMBIA
TELECOMUNICACIONES** cuando existe al menos una fila en el archivo de
COLOMBIA TELECOMUNICACIONES con la misma combinación de:

```text
LONGITUD
LATITUD
IDENT_SECT_ESTAC_BASE_POR_TEC
```

(y de forma simétrica para determinar si una fila de COLOMBIA
TELECOMUNICACIONES es compartida con COLOMBIA MÓVIL).

Antes de comparar, cada campo se normaliza así:

- `LONGITUD` y `LATITUD` se convierten a valores numéricos y se redondean a
  **6 decimales**, para evitar diferencias causadas únicamente por la
  representación de números de punto flotante.
- `IDENT_SECT_ESTAC_BASE_POR_TEC` se recorta de espacios al inicio/fin y se
  compara **como texto**.
- `BANDA_FRECUENCIA_OPERAC_SECTOR` se convierte a valor numérico (se usa
  solo para clasificar, no forma parte de la llave de cruce).

Una fila con valores nulos en cualquiera de los tres campos de la llave
(`LONGITUD`, `LATITUD`, `IDENT_SECT_ESTAC_BASE_POR_TEC`) **nunca** se
considera compartida. No se realizan cruces aproximados por distancia
geográfica: la coincidencia debe ser exacta sobre la llave normalizada.

La pertenencia se resuelve mediante un **conjunto de llaves únicas** de la
otra tabla (operación de pertenencia / `isin`), nunca mediante un `merge`
que pueda multiplicar filas cuando existan llaves duplicadas.

## Lógica de cada archivo de salida

Sea `banda` el valor numérico de `BANDA_FRECUENCIA_OPERAC_SECTOR` de cada
fila.

| Archivo     | Origen de las filas               | Condición                                                    |
|-------------|------------------------------------|---------------------------------------------------------------|
| `UT5.xlsx`  | COLOMBIA MÓVIL                     | `compartida_con_telecomunicaciones & (banda == 3580)`          |
| `UT.xlsx`   | COLOMBIA MÓVIL                     | `compartida_con_telecomunicaciones & (banda != 3580)`          |
| `CMO.xlsx`  | COLOMBIA MÓVIL                     | `no_compartida_con_telecomunicaciones & (banda != 3580)`       |
| `TEL.xlsx`  | COLOMBIA TELECOMUNICACIONES        | `no_compartida_con_colombia_movil & (banda != 3580)`           |

`UT5.xlsx` es el **único** archivo de salida que puede contener filas con
`BANDA_FRECUENCIA_OPERAC_SECTOR == 3580`. `UT.xlsx`, `CMO.xlsx` y
`TEL.xlsx` siempre excluyen la banda 3580. Esta invariante se verifica de
forma automática al finalizar el procesamiento.

Cada archivo de salida:

- Conserva **todas las columnas originales** y su **orden original**.
- No incluye columnas auxiliares usadas para la normalización o el cruce.
- Conserva **filas duplicadas** que ya existieran en el archivo fuente (no
  se eliminan duplicados).
- Conserva el **orden original de las filas**.
- Incluye una hoja llamada `PARAMET_TEC_SECTORES_ESTA_BASE`, incluso si el
  resultado no tiene filas (en ese caso se generan solo los encabezados).
- No exporta el índice de pandas.

## Instalación

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Ejecución local

```bash
streamlit run app.py
```

La aplicación abrirá en el navegador (por defecto en
`http://localhost:8501`). Desde la interfaz:

1. Cargue el archivo de COLOMBIA MÓVIL en el primer cargador.
2. Cargue el archivo de COLOMBIA TELECOMUNICACIONES en el segundo cargador.
3. Presione **Procesar archivos**.
4. Revise el resumen, la tabla de control y las vistas previas.
5. Descargue los archivos individuales o el ZIP con los cuatro resultados.

> Con archivos de ~100.000 filas, la lectura y generación de los Excel
> puede tardar entre 1 y 3 minutos; la interfaz mostrará un indicador de
> progreso mientras tanto.

## Ejecución de las pruebas

```bash
pytest
```

Las pruebas cubren, entre otros casos: clasificación correcta en cada uno
de los cuatro archivos, no duplicación de filas por llaves repetidas,
redondeo de coordenadas, llaves incompletas, conservación de encabezados
en resultados vacíos, ausencia de columnas auxiliares en la salida, y
conservación del orden original de filas y columnas.

## Estructura del proyecto

```text
app.py                  # Interfaz Streamlit (orquesta validación, cruce y exportación)
requirements.txt
README.md
.gitignore
pytest.ini
src/
    __init__.py
    processor.py         # Lógica de normalización, llave compuesta y clasificación
    validators.py         # Validaciones de archivo, hoja, columnas y valores
    exporters.py           # Generación de Excel y ZIP en memoria (BytesIO)
tests/
    test_processor.py       # Pruebas unitarias de la lógica de cruce
```

## Validaciones realizadas antes de procesar

1. Que se hayan cargado ambos archivos.
2. Que los archivos tengan extensión `.xlsx` o `.xls`.
3. Que ambos contengan la hoja `PARAMET_TEC_SECTORES_ESTA_BASE`.
4. Que ambos contengan las columnas `LONGITUD`, `LATITUD`,
   `IDENT_SECT_ESTAC_BASE_POR_TEC` y `BANDA_FRECUENCIA_OPERAC_SECTOR`.
5. Que los archivos se puedan leer correctamente (archivo no corrupto).
6. Que existan filas con valores válidos en los campos usados para el
   cruce.
7. Que la columna de banda tenga al menos un valor numérico convertible.

Si alguna validación falla, la interfaz muestra un mensaje claro indicando
en qué archivo ocurrió el problema, qué hoja o columnas faltan, o cuál fue
el problema de lectura. El detalle técnico (traceback) se registra
internamente mediante `logging` y no se muestra al usuario.

## Consideraciones sobre normalización de coordenadas

Los valores de `LONGITUD` y `LATITUD` en los archivos fuente pueden llegar
como texto o como número, y pueden tener pequeñas diferencias de
representación en punto flotante aunque describan la misma ubicación. Por
eso, antes de comparar:

- Se convierten explícitamente a numérico con `pandas.to_numeric` (los
  valores no convertibles quedan como nulos y su fila nunca se considera
  compartida).
- Se redondean a 6 decimales (~0.11 metros de precisión en el ecuador),
  suficiente para identificar la misma estación sin introducir cruces
  aproximados por distancia.
- El redondeo se aplica **solo** para efectos de comparación; los valores
  originales de `LONGITUD` y `LATITUD` exportados en los archivos finales
  nunca se modifican, ya que los archivos de salida son subconjuntos
  fieles de las filas originales.

## Notas

- No se incluyen archivos Excel reales ni datos personales en el
  repositorio (ver `.gitignore`).
- Los archivos cargados no se guardan en disco: se procesan en memoria
  usando `BytesIO`, tanto en la lectura como en la generación de los
  resultados y del ZIP.
