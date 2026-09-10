-- Extiende el tipo source_type con tres nuevos valores para:
--   pmge_projects     : proyectos derivados del documento PMGE
--   technology_agenda : agenda tecnológica derivada del documento PMGE
--   support_document  : documentos de apoyo misceláneos
--
-- Prerequisito: 0001_documents_and_jobs.sql debe estar aplicado.
-- Esta migración es idempotente: usa DO $$ ... IF NOT EXISTS para no fallar
-- si los valores ya existen (PostgreSQL 14+ soporta ADD VALUE IF NOT EXISTS).
--
-- NO ejecutar automáticamente contra producción.
-- Comando: scripts\supabase.cmd db push --dry-run (verificar primero)

begin;

do $$
begin
    if not exists (
        select 1 from pg_enum
        where enumtypid = 'source_type'::regtype
          and enumlabel = 'pmge_projects'
    ) then
        alter type source_type add value 'pmge_projects';
    end if;

    if not exists (
        select 1 from pg_enum
        where enumtypid = 'source_type'::regtype
          and enumlabel = 'technology_agenda'
    ) then
        alter type source_type add value 'technology_agenda';
    end if;

    if not exists (
        select 1 from pg_enum
        where enumtypid = 'source_type'::regtype
          and enumlabel = 'support_document'
    ) then
        alter type source_type add value 'support_document';
    end if;
end
$$;

-- Nota: ADD VALUE no se puede ejecutar dentro de una transacción con otras DDL
-- en PostgreSQL < 12. En PostgreSQL 14+ (usado por Supabase) sí funciona.
-- Si falla por restricción de transacción, ejecutar cada ALTER TYPE por separado
-- fuera de BEGIN/COMMIT.

commit;
