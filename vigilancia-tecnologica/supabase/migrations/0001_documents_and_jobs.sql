-- Base documental y jobs para la arquitectura Supabase/PostgreSQL.
-- Esta migracion no crea politicas RLS: con RLS habilitado y sin policies,
-- el acceso desde clientes queda bloqueado. El backend futuro debera usar
-- credenciales autorizadas y definir policies/grants en una migracion posterior.

begin;

create extension if not exists pgcrypto;

create type source_type as enum (
    'surveillance',
    'institutional_plan',
    'policy_matrix',
    'pmge_projects',
    'technology_agenda',
    'support_document'
);

create type document_status as enum (
    'uploaded',
    'preparing',
    'prepared',
    'analyzing',
    'validating',
    'ready_to_persist',
    'processed',
    'failed'
);

create type job_type as enum (
    'document_preparation',
    'document_analysis',
    'institutional_plan_analysis',
    'policy_matrix_analysis',
    'evidence_validation',
    'result_persistence'
);

create type job_status as enum (
    'queued',
    'running',
    'completed',
    'failed'
);

create table documents (
    id uuid primary key default gen_random_uuid(),
    file_name text not null,
    file_type text not null,
    source_type source_type not null,
    file_hash text not null,
    storage_bucket text,
    storage_path text,
    document_date date,
    status document_status not null,
    version integer not null default 1,
    replaces_id uuid references documents(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint documents_file_hash_unique unique (file_hash),
    constraint documents_file_name_not_blank check (length(btrim(file_name)) > 0),
    constraint documents_file_type_not_blank check (length(btrim(file_type)) > 0),
    constraint documents_file_hash_not_blank check (length(btrim(file_hash)) > 0),
    constraint documents_version_positive check (version > 0),
    constraint documents_storage_path_requires_bucket check (
        storage_path is null or storage_bucket is not null
    )
);

create table document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete restrict,
    content text not null,
    page_number integer,
    section_title text,
    sheet_name text,
    row_reference text,
    content_hash text not null,
    position integer not null,
    constraint document_chunks_document_position_unique unique (document_id, position),
    constraint document_chunks_page_number_positive check (
        page_number is null or page_number > 0
    ),
    constraint document_chunks_position_non_negative check (position >= 0),
    constraint document_chunks_content_hash_not_blank check (
        length(btrim(content_hash)) > 0
    )
);

create table processing_jobs (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete restrict,
    job_type job_type not null,
    status job_status not null,
    prompt_id text,
    prompt_version text,
    attempts integer not null default 0,
    error_message text,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint processing_jobs_attempts_non_negative check (attempts >= 0),
    constraint processing_jobs_prompt_version_requires_prompt check (
        prompt_version is null or prompt_id is not null
    )
);

create index documents_source_type_status_idx
    on documents (source_type, status);

create index documents_status_created_at_idx
    on documents (status, created_at);

create index documents_replaces_id_idx
    on documents (replaces_id)
    where replaces_id is not null;

create index document_chunks_document_page_idx
    on document_chunks (document_id, page_number)
    where page_number is not null;

create index document_chunks_document_sheet_row_idx
    on document_chunks (document_id, sheet_name, row_reference)
    where sheet_name is not null or row_reference is not null;

create index document_chunks_content_hash_idx
    on document_chunks (content_hash);

create index processing_jobs_document_status_idx
    on processing_jobs (document_id, status);

create index processing_jobs_type_status_idx
    on processing_jobs (job_type, status);

create unique index processing_jobs_active_unique_idx
    on processing_jobs (document_id, job_type)
    where status in ('queued', 'running');

create or replace function set_documents_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger documents_set_updated_at
before update on documents
for each row
execute function set_documents_updated_at();

alter table documents enable row level security;
alter table document_chunks enable row level security;
alter table processing_jobs enable row level security;

commit;
