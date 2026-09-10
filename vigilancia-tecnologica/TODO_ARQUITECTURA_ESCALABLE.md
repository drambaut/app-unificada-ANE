# TODO arquitectura escalable ANE

Este checklist aterriza la arquitectura planeada en pasos ejecutables. La idea es avanzar una tarea a la vez, validar, y solo despues pasar a la siguiente.

## Estado base

- [x] Rama de trabajo: `feature/scalable-architecture`.
- [x] Contratos JSON Schema.
- [x] Prompts versionados.
- [x] Cliente Gemini modular con `response_schema`.
- [x] Preparacion tecnica PDF/Excel.
- [x] Dominio documental con estados y jobs.
- [x] Validacion de evidencia.
- [x] Normalizacion de resultados.
- [x] Snapshots inmutables.
- [x] Analisis transversal.
- [x] Scoring 0-100.
- [x] Publicacion versionada.
- [x] Modelo de lectura para dashboard.
- [x] Migraciones SQL offline en `supabase/migrations`.

## 1. Ambiente local

- [x] Crear o activar entorno Python 3.12.
- [x] Instalar dependencias con `pip install -r requirements.txt`.
- [x] Fijar `pymupdf==1.24.14` si el entorno Windows vuelve a fallar con PyMuPDF.
- [x] Correr `python -m pytest`.
- [x] Resolver fallos de tests antes de tocar infraestructura.

## 2. Supabase proyecto e infraestructura

- [x] Instalar Supabase CLI.
- [x] Ejecutar `supabase login`.
- [x] Crear proyecto Supabase o usar uno existente.
- [x] Inicializar configuracion local si hace falta: `supabase init`.
- [x] Vincular repo con proyecto remoto: `supabase link`.
- [x] Hacer dry run de migraciones: `supabase db push --dry-run`.
- [x] Aplicar migraciones: `supabase db push`.
- [x] Verificar tablas, enums, funciones y vista `current_dashboard_publication`.

Nota: Supabase CLI quedo instalado localmente en `.tools/supabase/` y se ejecuta con `scripts\supabase.cmd`. `winget` falla al iniciar desde esta sesion y no estan disponibles `npm`, `scoop` ni `choco`, por eso se uso el binario oficial de Windows descargado desde GitHub Releases.

## 3. Storage

- [x] Definir bucket para documentos originales, por ejemplo `source-documents`.
- [x] Crear bucket en Supabase Storage.
- [x] Definir convencion de rutas:
  `source_type/document_id/original_filename`.
- [x] Agregar settings para bucket y rutas.
- [x] Implementar adaptador de Storage.
- [x] Hacer prueba de subida y lectura con PDF/Excel pequeno.

## 4. Dependencias y settings Supabase

- [x] Agregar dependencia Python de Supabase en `requirements.txt`.
- [x] Agregar variables esperadas a `.env.example` si existe o documentarlas en README:
  `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`.
- [x] Decidir uso de `service_role` solo en backend seguro.
- [x] Mantener `.env` fuera de Git.

## 5. Repositorios Supabase

- [x] Implementar `SupabaseDocumentRepository`.
- [x] Implementar `SupabaseResultRepository`.
- [x] Implementar `SupabaseCorpusSnapshotRepository`.
- [x] Implementar `SupabaseAnalysisRunRepository`.
- [x] Implementar repositorios de lectura para `DashboardReadService`.
- [x] Cubrir operaciones atomicas criticas con RPC o SQL transaccional.
- [x] Agregar tests con fakes o integration tests marcados aparte.

## 6. Workflow de carga manual

- [x] Crear servicio de carga que reciba archivo, tipo de fuente y metadata.
- [x] Subir archivo original a Supabase Storage.
- [x] Registrar documento con `storage_path` real.
- [x] Ejecutar preparacion tecnica.
- [x] Ejecutar Gemini con contrato correspondiente.
- [x] Validar evidencia.
- [x] Persistir resultados en Supabase PostgreSQL.
- [x] Manejar errores dejando documento/job en `failed`.

## 7. Analisis transversal con datos reales

- [x] Consultar documentos `processed` desde Supabase.
- [x] Construir snapshot inmutable con registros reales.
- [x] Ejecutar `thematic_landscape`.
- [x] Ejecutar `regulatory_intelligence`.
- [x] Ejecutar `strategic_assessment`.
- [x] Aplicar scoring matematico.
- [x] Publicar solo si las tres etapas completan.
- [x] Verificar historico de publicaciones.

Nota: smoke transversal real completado y publicado en Supabase.
Primer snapshot publicado con 2 documentos: `dace30dc-c056-45e8-8933-af0fbef20aab`.
Primer run publicado: `0e531833-9f11-4b9f-8640-c23b034b2a3a`.
Snapshot vigente con 3 documentos: `226ceb5f-bb7e-4c1b-914a-f5f90d08400b`.
Run publicado vigente: `9ea747ce-3aaa-4a01-b372-b9a3b2b4f59e`.
Snapshot vigente con 4 documentos: `548ed8a0-d2ec-491d-a465-070a1e373f22`.
Run publicado vigente con `policy_matrix`: `6b76d1a4-688f-4e94-9ea0-0359a474f402`.

## 8. Dashboard nuevo

- [x] Cambiar Streamlit para leer `DashboardReadService`.
- [x] Eliminar dependencia del dashboard principal sobre `demo_data`.
- [x] Mostrar solo la publicacion vigente.
- [x] Mostrar estado amigable si no hay publicacion.
- [x] Mantener `demo_data` como modo demo separado si sigue siendo util.
- [x] Validar que el dashboard no llame Gemini ni lea archivos originales.

Nota: `DASHBOARD_DATA_SOURCE=auto` usa Supabase cuando hay `SUPABASE_URL` y
`SUPABASE_KEY`; si no, cae a modo demo para mantener viva la vista actual en
Render hasta publicar datos reales.

## 9. Seguridad y RLS

Fuera de alcance para esta entrega por decision de proyecto.

La entrega actual queda enfocada en:

- Dashboard funcionando.
- Documentos precargados/procesados.
- Carga publica temporal de documentos desde el dashboard.
- Procesamiento basico del corpus mediante dashboard y herramienta interna/scripts.
- Conexion del dashboard con Supabase.

Roles, autenticacion de usuarios y pruebas con perfiles quedan como mejora
futura si negocio lo solicita.

## 10. Corpus inicial y despliegue

- [x] Crear runner operativo para cargar/procesar archivos reales:
  `python run_manual_processing.py`.
- [x] Crear smoke check operativo para Supabase:
  `python run_supabase_healthcheck.py`.
- [x] Inventariar corpus inicial recibido:
  `INVENTARIO_CORPUS_INICIAL.md`.
- [x] Preparar documentos iniciales.
- [x] Procesar smoke de vigilancia PDF.
- [x] Procesar smoke de PMGE/Agenda.
- [x] Procesar smoke de Excel consolidado de vigilancia.
- [x] Confirmar archivo candidato para `policy_matrix`.
- [x] Procesar smoke de `policy_matrix`.
- [x] Definir estrategia de corpus completo: alcance, prioridad, costos Gemini y tiempos.
- [x] Crear manifiesto de procesamiento por lotes con:
  `path`, `source_type`, `provider`, `priority`, `batch_id`, `status`, `notes`.
- [x] Separar corpus en lotes seguros:
  piloto 5-10 archivos, luego lotes de 20-50 segun costo/tiempo.
- [x] Implementar o documentar control operativo de lotes:
  limite por corrida, detener por error, resumen de fallidos y reanudacion.
- [x] Ejecutar `dry-run` del primer lote antes de consumir Gemini.
- [ ] Reintentar fallidos del lote piloto y validar resultados en Supabase.
- [ ] Procesar corpus inicial completo por lotes aprobados.
- [ ] Reintentar documentos `failed` por lote sin repetir todo el pipeline.
- [ ] Generar analisis transversal final con el corpus completo procesado.
- [x] Generar primer analisis transversal.
- [x] Publicar primera version.
- [ ] Configurar variables de entorno en Render:
  `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
  `SUPABASE_STORAGE_BUCKET`, `DASHBOARD_DATA_SOURCE=supabase`.
- [x] Implementar carga publica temporal de PDF/Excel desde dashboard.
- [x] Agregar limites basicos a la carga publica:
  tipos PDF/XLS/XLSX, metadata minima, modo smoke y mensajes de error.
- [ ] Hacer merge/pull request de `feature/scalable-architecture` hacia la rama usada por Render.
- [ ] Desplegar app en Render desde la rama final.
- [ ] Validar que el dashboard desplegado lee la publicacion vigente desde Supabase.
- [x] Validar fallback a demo cuando faltan variables Supabase.
- [x] Hacer smoke test de carga, analisis y dashboard.

Nota: el primer smoke real de procesamiento individual quedo exitoso con
`FLSPAR20250003_Enacom_reduces_bandwidth_of_mobile_satellite_services_using_.pdf`;
Supabase registro el documento `7a6a01a0-4acd-46e7-bb91-1afd2a69980c` en estado
`processed`. El smoke institucional tambien quedo exitoso con
`PMGE20262030yAgendaRegulatoriaANE_Mar2026.pdf`; Supabase registro el documento
`eb52f1bf-c37b-4946-bb83-1019a2104d42` en estado `processed`.
El smoke de Excel consolidado de vigilancia tambien quedo exitoso con
`matriz_vigilancia_ampliada_Agenda_2027_2028.xlsx`; Supabase registro el
documento `b5832e15-8604-473e-ab29-8b63b595932f` en estado `processed`.
El smoke de matriz de politicas tambien quedo exitoso con
`Plan Estrategico 2025-2028 con planes tactico.xlsx`; Supabase registro el
documento `c27b9012-be1d-46ef-951d-780e64c1ea4d` en estado `processed`.
Healthcheck estricto posterior al analisis transversal con `policy_matrix`:
`Documentos processed: 4`, publicacion vigente
`6b76d1a4-688f-4e94-9ea0-0359a474f402`.

Manifiesto operativo generado en `outputs/corpus_processing_manifest.csv`:
625 archivos soportados por el pipeline actual, distribuidos en 25 lotes de 25.
Para piloto controlado se puede ejecutar `batch-001 --limit 10 --skip-existing`;
como los 4 primeros ya estan procesados, esto procesa hasta 6 documentos nuevos.
Los 20 archivos restantes del inventario son PPTX, ZIP, DOCX o PNG y requieren
preparadores futuros. El `batch-001` ya fue validado con `dry-run`.
La ejecucion real del piloto debe correrse localmente por el usuario porque
envia documentos reales a Gemini:
`scripts\run_corpus_manifest_batch_with_supabase_env.cmd outputs\corpus_processing_manifest.csv --batch-id batch-001 --limit 10 --skip-existing --report-csv outputs\corpus_batch-001_pilot_report.csv`.
Resultado piloto inicial: 3 procesados, 2 fallidos y 5 omitidos sobre 10.
Reporte: `outputs/corpus_batch-001_pilot_report.csv`. Se ajusto la validacion
de `row_reference` para Excel y el retry de `failed` con `--reset-failed`.
Primer retry del piloto: 0 procesados, 4 fallidos y 6 omitidos sobre 10.
Se ajusto evidencia parcial por hoja/pagina, desambiguacion de `canonical_key`
duplicada y soporte `--smoke`/`--metadata` en el runner de manifiesto.
Siguiente retry recomendado:
`scripts\run_corpus_manifest_batch_with_supabase_env.cmd outputs\corpus_processing_manifest.csv --batch-id batch-001 --limit 10 --smoke --reset-failed --skip-existing --report-csv outputs\corpus_batch-001_pilot_retry2_report.csv`.
Segundo retry del piloto: 2 procesados, 2 fallidos y 6 omitidos sobre 10.
Quedan fallidos `Documento-Tendencias-2025.pdf` por JSON invalido de Gemini y
`Monitoreo-Tendencias-2024.pdf` por evidencia PDF no encontrada. Se redujo aun
mas el modo smoke de vigilancia y se flexibilizo evidencia parcial por pagina.
Tercer retry del piloto: 1 procesado, 1 fallido y 8 omitidos sobre 10.
El piloto queda funcional con 9/10 documentos cubiertos. El unico fallido
controlado es `Monitoreo-Tendencias-2024.pdf` por evidencia PDF no encontrada.
Resto de `batch-001`: 11 procesados, 3 fallidos y 1 omitido sobre 15.
Los 3 fallidos compartian error de preparacion por caracter NUL (`\u0000`) no
aceptado por PostgreSQL. Se agrego limpieza tecnica de texto antes de persistir
chunks PDF/Excel.
Retry del resto de `batch-001`: 2 procesados, 0 fallidos y 13 omitidos sobre 15.
El bloque `batch-001 --offset 10` queda limpio.
El analisis transversal con 23 documentos fallo inicialmente por JSON truncado
en `thematic_landscape`. Se agrego modo transversal `--bounded-context` con
limites de contexto y salida resumida para publicar dashboard con corpus
creciente sin convertir la corrida en demo. Tambien se acotaron los contratos
transversales y se agrego retry automatico de Gemini cuando devuelve JSON
truncado o invalido. Para evitar `400 INVALID_ARGUMENT` de Gemini por schemas
demasiado restrictivos, el proveedor recibe un schema liviano y Python conserva
la validacion/recorte local con el contrato completo. Si Gemini devuelve JSON
invalido solo en `strategic_assessment`, se guarda una evaluacion estrategica
vacia valida para no inventar scores desde Python y permitir publicar las etapas
transversales previas. Si el cupo de Gemini queda agotado, usar
`--empty-strategic-assessment` para completar esa etapa sin llamar Gemini.
Si una ejecucion queda activa para el mismo snapshot, usar:
`scripts\run_supabase_transversal_with_supabase_env.cmd --bounded-context --retry-active`.
Run transversal recuperado y publicado con corpus creciente:
`0963e951-2153-434f-a7c2-3f283315cc92`, snapshot
`b1c5a5f1-5f9a-4627-abd3-96157fa3801e`.
Nueva corrida transversal publicada con `gemini-3.5-flash`:
`99a5c5d8-f9a9-4ff3-8c21-ca1b766603cc`, snapshot
`b1c5a5f1-5f9a-4627-abd3-96157fa3801e`.
Carga publica temporal implementada en dashboard modo Supabase: acepta PDF,
XLS y XLSX, pide tipo de fuente y proveedor, procesa en modo smoke por defecto
y muestra errores controlados por etapa. Los documentos cargados quedan
procesados en Supabase; para verlos en el dashboard vigente se debe publicar un
nuevo analisis transversal.

## Primera tarea recomendada

Empezar por `1. Ambiente local`: crear entorno Python 3.12, instalar dependencias y correr tests. Sin esa base, cualquier cambio de Supabase queda mas dificil de validar.
