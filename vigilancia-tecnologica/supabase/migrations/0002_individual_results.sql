-- Resultados individuales normalizados.
-- Debe ejecutarse despues de 0001_documents_and_jobs.sql.
-- Los resultados son append-only: reprocesar debe crear nuevos registros y,
-- cuando aplique, una nueva version documental; no se sobrescriben historicos.
-- RLS queda habilitado sin policies/grants, por lo que el acceso cliente queda
-- bloqueado hasta una migracion de seguridad posterior.

begin;

create type confidence_level as enum (
    'Alta',
    'Media',
    'Baja'
);

create type extraction_basis as enum (
    'explicit',
    'inferred',
    'mixed'
);

create type result_record_type as enum (
    'document_analysis',
    'finding',
    'evidence',
    'pmge_project',
    'pmge_objective',
    'pmge_activity',
    'agenda_initiative',
    'agenda_deliverable',
    'policy',
    'policy_activity',
    'policy_commitment'
);

create table result_records (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete restrict,
    record_type result_record_type not null,
    data jsonb not null,
    prompt_id text not null,
    prompt_version text not null,
    contract_name text not null,
    model_name text not null,
    canonical_key text not null,
    confidence confidence_level,
    extraction_basis extraction_basis,
    content_hash text not null,
    record_version text not null,
    created_at timestamptz not null default now(),
    constraint result_records_canonical_key_unique unique (canonical_key),
    constraint result_records_data_object check (jsonb_typeof(data) = 'object'),
    constraint result_records_prompt_id_not_blank check (length(btrim(prompt_id)) > 0),
    constraint result_records_prompt_version_not_blank check (length(btrim(prompt_version)) > 0),
    constraint result_records_contract_name_not_blank check (length(btrim(contract_name)) > 0),
    constraint result_records_model_name_not_blank check (length(btrim(model_name)) > 0),
    constraint result_records_canonical_key_not_blank check (length(btrim(canonical_key)) > 0),
    constraint result_records_content_hash_sha256 check (content_hash ~ '^[0-9a-f]{64}$'),
    constraint result_records_record_version_not_blank check (length(btrim(record_version)) > 0)
);

create table document_analysis (
    id uuid primary key references result_records(id) on delete restrict,
    document_type text not null,
    title text not null,
    summary text not null,
    publication_date text,
    document_date text,
    language text,
    preliminary_topics text[] not null default '{}',
    technologies text[] not null default '{}',
    frequency_bands text[] not null default '{}',
    countries_regions text[] not null default '{}',
    organizations text[] not null default '{}',
    actors text[] not null default '{}',
    keywords text[] not null default '{}',
    constraint document_analysis_title_not_blank check (length(btrim(title)) > 0)
);

create table findings (
    id uuid primary key references result_records(id) on delete restrict,
    finding_type text not null,
    title text not null,
    description text not null,
    preliminary_topics text[] not null default '{}',
    technologies text[] not null default '{}',
    frequency_bands text[] not null default '{}',
    countries_regions text[] not null default '{}',
    organizations text[] not null default '{}',
    constraint findings_title_not_blank check (length(btrim(title)) > 0),
    constraint findings_type_not_blank check (length(btrim(finding_type)) > 0)
);

create table evidence (
    id uuid primary key references result_records(id) on delete restrict,
    quote text not null,
    evidence_type text not null,
    page_number integer,
    sheet_name text,
    row_reference text,
    section_title text,
    matched_chunk_id uuid references document_chunks(id) on delete restrict,
    constraint evidence_quote_not_blank check (length(btrim(quote)) > 0),
    constraint evidence_quote_max_length check (char_length(quote) <= 500),
    constraint evidence_page_number_positive check (page_number is null or page_number > 0),
    constraint evidence_type_not_blank check (length(btrim(evidence_type)) > 0)
);

create table result_record_evidence (
    record_id uuid not null references result_records(id) on delete restrict,
    evidence_id uuid not null references evidence(id) on delete restrict,
    primary key (record_id, evidence_id)
);

create or replace function validate_result_record_type(
    expected_type result_record_type,
    record_id uuid
)
returns void
language plpgsql
as $$
declare
    actual_type result_record_type;
begin
    select record_type
    into actual_type
    from result_records
    where id = record_id;

    if actual_type is null then
        raise exception 'result_record % does not exist', record_id;
    end if;

    if actual_type <> expected_type then
        raise exception 'result_record % has type %, expected %', record_id, actual_type, expected_type;
    end if;
end;
$$;

create or replace function validate_document_analysis_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('document_analysis', new.id);
    return new;
end;
$$;

create or replace function validate_findings_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('finding', new.id);
    return new;
end;
$$;

create or replace function validate_evidence_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('evidence', new.id);
    return new;
end;
$$;

create or replace function validate_result_record_evidence()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('evidence', new.evidence_id);
    return new;
end;
$$;

create trigger document_analysis_validate_record_type
before insert on document_analysis
for each row
execute function validate_document_analysis_record_type();

create trigger findings_validate_record_type
before insert on findings
for each row
execute function validate_findings_record_type();

create trigger evidence_validate_record_type
before insert on evidence
for each row
execute function validate_evidence_record_type();

create trigger result_record_evidence_validate_evidence_type
before insert on result_record_evidence
for each row
execute function validate_result_record_evidence();

create index result_records_document_type_idx
    on result_records (document_id, record_type);

create index result_records_content_hash_idx
    on result_records (content_hash);

create index result_records_created_at_idx
    on result_records (created_at);

create index result_records_finding_confidence_idx
    on result_records (confidence)
    where record_type = 'finding';

create index result_records_evidence_document_idx
    on result_records (document_id)
    where record_type = 'evidence';

create index findings_type_confidence_idx
    on findings (finding_type);

create index evidence_matched_chunk_idx
    on evidence (matched_chunk_id)
    where matched_chunk_id is not null;

create index evidence_page_location_idx
    on evidence (page_number)
    where page_number is not null;

create index evidence_sheet_row_location_idx
    on evidence (sheet_name, row_reference)
    where sheet_name is not null or row_reference is not null;

create index result_record_evidence_evidence_idx
    on result_record_evidence (evidence_id);

alter table result_records enable row level security;
alter table document_analysis enable row level security;
alter table findings enable row level security;
alter table evidence enable row level security;
alter table result_record_evidence enable row level security;

commit;
