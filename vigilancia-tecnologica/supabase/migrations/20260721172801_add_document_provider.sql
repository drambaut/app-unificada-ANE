-- Agrega la columna provider (fuente/organizacion de origen) a documents.
-- Se captura en el momento de la carga (campo "Proveedor / origen" del
-- dashboard) para poder mostrarla despues sin depender de un archivo local
-- (outputs/corpus_processing_manifest.csv), que no existe en produccion.
--
-- Idempotente: usa IF NOT EXISTS para poder reaplicarse sin error.

begin;

alter table documents
add column if not exists provider text;

commit;
