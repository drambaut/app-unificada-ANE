# Inventario corpus inicial

Carpeta revisada:

```text
Vigilanciatecnologica_data/Vigilancia tecnologica
```

La carpeta esta ignorada por Git mediante `.gitignore`.

## Conteo tecnico

- Total archivos revisados: 645
- PDF: 621
- Excel: 4
- PowerPoint: 12
- ZIP: 6
- DOCX: 1
- PNG: 1

Distribucion principal:

- CRC: 2 PDF
- Cullen International: 206 PDF
- ejercicio preliminar: 2 Excel
- GSMA: 7 PDF
- NERA: 1 PDF
- Omdia: 155 PDF, 12 PPTX y 1 Excel
- PolicyTracker: 198 PDF y 1 PNG
- Politicas Nacionales: 5 PDF, 1 Excel y 1 DOCX
- Reguladores: 24 PDF y 6 ZIP
- UIT: 21 PDF
- WorldBank: 2 PDF

## Excel revisados

### `ejercicio preliminar/matriz_vigilancia_ampliada_Agenda_2027_2028.xlsx`

Clasificacion recomendada: `surveillance`.

Contiene matriz ampliada de vigilancia tecnologica con tendencias oficiales,
fuentes oficiales, priorizacion, cruces con radar, validacion tecnica, catalogo
de fuentes, hallazgos, temas PolicyTracker y cruces con Agenda/PMGE.

No parece una matriz de politicas publicas pura. Es mejor tratarla como fuente
de vigilancia consolidada/priorizada.

### `ejercicio preliminar/vigilancia_tecnologica_News_DPL_TeleSemana_Agenda_2027_2028.xlsx`

Clasificacion recomendada: `surveillance`.

Contiene base de noticias DPL/TeleSemana, temas consolidados y fuentes
primarias para validacion. Es claramente vigilancia tecnologica sectorial.

### `Omdia/Fiber Homes Passed Tracker - 4Q25.xlsx`

Clasificacion recomendada: `surveillance`, si se decide usarlo.

Es un tracker de mercado de fibra/hogares pasados. No corresponde a PMGE,
Agenda ni matriz de politicas publicas.

### `Politicas Nacionales/Plan Estrategico 2025-2028 con planes tactico.xlsx`

Clasificacion recomendada provisional: pendiente de validacion.

Contiene plan estrategico, plan tactico y POA de la ANE. Puede servir como
insumo institucional, pero no es evidente que sea la `policy_matrix` esperada
por el contrato actual, que busca politicas, actividades y compromisos.

Antes de procesarlo como `policy_matrix`, confirmar con negocio si este archivo
representa la matriz de politicas publicas requerida por la arquitectura.

## Clasificacion propuesta por fuente

### `surveillance`

Usar documentos de vigilancia tecnologica/regulatoria de:

- `CRC`
- `Cullen International`
- `ejercicio preliminar`
- `GSMA`
- `NERA`
- `Omdia`
- `PolicyTracker`
- `Reguladores`
- `UIT`
- `WorldBank`

Smoke real ya exitoso:

```text
Cullen International/FLSPAR20250003_Enacom_reduces_bandwidth_of_mobile_satellite_services_using_.pdf
document_id=7a6a01a0-4acd-46e7-bb91-1afd2a69980c
status=processed

ejercicio preliminar/matriz_vigilancia_ampliada_Agenda_2027_2028.xlsx
document_id=b5832e15-8604-473e-ab29-8b63b595932f
status=processed
```

### `institutional_plan`

Documento candidato claro y ya procesado:

```text
Politicas Nacionales/PMGE20262030yAgendaRegulatoriaANE_Mar2026.pdf
document_id=eb52f1bf-c37b-4946-bb83-1019a2104d42
status=processed
```

### `policy_matrix`

Pendiente de confirmacion. No hay un archivo claramente nombrado como matriz de
politicas publicas.

Candidato mas cercano:

```text
Politicas Nacionales/Plan Estrategico 2025-2028 con planes tactico.xlsx
```

Riesgo: el contrato `policy_matrix_extraction` espera politicas, actividades y
compromisos. Si este Excel es planeacion interna o POA, no conviene etiquetarlo
como `policy_matrix` sin validacion de negocio.

## Recomendacion de procesamiento

Para smoke de arquitectura:

- Ya existen 2 documentos `surveillance` procesados.
- Ya existe 1 documento `institutional_plan` procesado.
- Se puede ejecutar el analisis transversal con esos tres insumos.
- Snapshot vigente publicado con 3 documentos:
  `226ceb5f-bb7e-4c1b-914a-f5f90d08400b`.
- Run vigente publicado:
  `9ea747ce-3aaa-4a01-b372-b9a3b2b4f59e`.

Para robustecer el smoke antes del corpus completo:

- Procesar uno de los Excel de `ejercicio preliminar` como `surveillance`.
- Confirmar con Daniel si `Plan Estrategico 2025-2028 con planes tactico.xlsx`
  debe tratarse como `policy_matrix`.

No procesar los 645 archivos de una sola corrida hasta que el smoke transversal
quede publicado y revisado.
