-- Snapshots del corpus, analisis transversal y publicacion vigente.
-- Debe ejecutarse despues de 0001, 0002 y 0003.
-- Los snapshots son append-only. La publicacion conserva historico y solo
-- actualiza is_current para cambiar atomicamente la ejecucion visible al dashboard.

begin;

create type analysis_run_status as enum (
    'queued',
    'running',
    'completed',
    'failed',
    'published'
);

create type analysis_stage as enum (
    'thematic_landscape',
    'regulatory_intelligence',
    'strategic_assessment'
);

create type analysis_stage_status as enum (
    'queued',
    'running',
    'completed',
    'failed'
);

create table corpus_snapshots (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    snapshot_hash text not null,
    selection_criteria jsonb not null,
    metadata jsonb not null default '{}'::jsonb,
    constraint corpus_snapshots_snapshot_hash_unique unique (snapshot_hash),
    constraint corpus_snapshots_hash_not_blank check (length(btrim(snapshot_hash)) > 0),
    constraint corpus_snapshots_selection_criteria_object check (jsonb_typeof(selection_criteria) = 'object'),
    constraint corpus_snapshots_metadata_object check (jsonb_typeof(metadata) = 'object')
);

create table corpus_snapshot_documents (
    snapshot_id uuid not null references corpus_snapshots(id) on delete restrict,
    document_id uuid not null references documents(id) on delete restrict,
    source_type source_type not null,
    primary key (snapshot_id, document_id)
);

create table corpus_snapshot_record_refs (
    snapshot_id uuid not null references corpus_snapshots(id) on delete restrict,
    record_id uuid not null references result_records(id) on delete restrict,
    document_id uuid not null references documents(id) on delete restrict,
    record_type result_record_type not null,
    canonical_key text not null,
    content_hash text not null,
    record_version text not null,
    created_at timestamptz not null,
    constraint corpus_snapshot_record_refs_unique unique (snapshot_id, record_id),
    constraint corpus_snapshot_record_refs_canonical_key_not_blank check (length(btrim(canonical_key)) > 0),
    constraint corpus_snapshot_record_refs_content_hash_sha256 check (content_hash ~ '^[0-9a-f]{64}$'),
    constraint corpus_snapshot_record_refs_record_version_not_blank check (length(btrim(record_version)) > 0)
);

create table analysis_runs (
    id uuid primary key default gen_random_uuid(),
    corpus_snapshot_id uuid not null references corpus_snapshots(id) on delete restrict,
    status analysis_run_status not null,
    attempts integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    published_at timestamptz,
    failed_at timestamptz,
    error_message text,
    constraint analysis_runs_attempts_non_negative check (attempts >= 0),
    constraint analysis_runs_published_requires_published_at check (
        status <> 'published' or published_at is not null
    )
);

create table analysis_stage_runs (
    id uuid primary key default gen_random_uuid(),
    analysis_run_id uuid not null references analysis_runs(id) on delete restrict,
    stage analysis_stage not null,
    status analysis_stage_status not null,
    prompt_id text not null,
    prompt_version text not null,
    contract_name text not null,
    attempts integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    failed_at timestamptz,
    error_message text,
    result_payload jsonb,
    constraint analysis_stage_runs_unique_stage unique (analysis_run_id, stage),
    constraint analysis_stage_runs_attempts_non_negative check (attempts >= 0),
    constraint analysis_stage_runs_prompt_id_not_blank check (length(btrim(prompt_id)) > 0),
    constraint analysis_stage_runs_prompt_version_not_blank check (length(btrim(prompt_version)) > 0),
    constraint analysis_stage_runs_contract_name_not_blank check (length(btrim(contract_name)) > 0),
    constraint analysis_stage_runs_payload_object check (
        result_payload is null or jsonb_typeof(result_payload) = 'object'
    ),
    constraint analysis_stage_runs_completed_requires_payload check (
        status <> 'completed' or result_payload is not null
    )
);

create table dashboard_publications (
    id uuid primary key default gen_random_uuid(),
    analysis_run_id uuid not null references analysis_runs(id) on delete restrict,
    snapshot_id uuid not null references corpus_snapshots(id) on delete restrict,
    published_at timestamptz not null default now(),
    is_current boolean not null default true,
    constraint dashboard_publications_analysis_run_unique unique (analysis_run_id)
);

create or replace function validate_snapshot_document_source_type()
returns trigger
language plpgsql
as $$
declare
    actual_source_type source_type;
begin
    select source_type
    into actual_source_type
    from documents
    where id = new.document_id;

    if actual_source_type is null then
        raise exception 'document % does not exist', new.document_id;
    end if;

    if actual_source_type <> new.source_type then
        raise exception 'snapshot document % has source_type %, expected %',
            new.document_id,
            new.source_type,
            actual_source_type;
    end if;

    return new;
end;
$$;

create or replace function validate_snapshot_record_ref()
returns trigger
language plpgsql
as $$
declare
    actual_document_id uuid;
    actual_record_type result_record_type;
    actual_canonical_key text;
    actual_content_hash text;
    actual_record_version text;
begin
    select document_id, record_type, canonical_key, content_hash, record_version
    into actual_document_id, actual_record_type, actual_canonical_key, actual_content_hash, actual_record_version
    from result_records
    where id = new.record_id;

    if actual_document_id is null then
        raise exception 'result_record % does not exist', new.record_id;
    end if;

    if actual_document_id <> new.document_id
        or actual_record_type <> new.record_type
        or actual_canonical_key <> new.canonical_key
        or actual_content_hash <> new.content_hash
        or actual_record_version <> new.record_version then
        raise exception 'snapshot record ref % does not match frozen result_record values', new.record_id;
    end if;

    return new;
end;
$$;

create or replace function set_analysis_runs_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create or replace function set_analysis_stage_runs_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger corpus_snapshot_documents_validate_source_type
before insert on corpus_snapshot_documents
for each row
execute function validate_snapshot_document_source_type();

create trigger corpus_snapshot_record_refs_validate_frozen_values
before insert on corpus_snapshot_record_refs
for each row
execute function validate_snapshot_record_ref();

create trigger analysis_runs_set_updated_at
before update on analysis_runs
for each row
execute function set_analysis_runs_updated_at();

create trigger analysis_stage_runs_set_updated_at
before update on analysis_stage_runs
for each row
execute function set_analysis_stage_runs_updated_at();

create unique index analysis_runs_active_snapshot_unique_idx
    on analysis_runs (corpus_snapshot_id)
    where status in ('queued', 'running');

create unique index dashboard_publications_current_unique_idx
    on dashboard_publications (is_current)
    where is_current;

create index corpus_snapshots_snapshot_hash_idx
    on corpus_snapshots (snapshot_hash);

create index corpus_snapshot_documents_document_idx
    on corpus_snapshot_documents (document_id);

create index corpus_snapshot_record_refs_snapshot_type_idx
    on corpus_snapshot_record_refs (snapshot_id, record_type);

create index corpus_snapshot_record_refs_record_idx
    on corpus_snapshot_record_refs (record_id);

create index analysis_runs_snapshot_status_idx
    on analysis_runs (corpus_snapshot_id, status);

create index analysis_stage_runs_run_stage_idx
    on analysis_stage_runs (analysis_run_id, stage);

create index dashboard_publications_run_idx
    on dashboard_publications (analysis_run_id);

create or replace function publish_analysis_run(target_analysis_run_id uuid)
returns uuid
language plpgsql
as $$
declare
    target_snapshot_id uuid;
    publication_id uuid;
    completed_stage_count integer;
begin
    select corpus_snapshot_id
    into target_snapshot_id
    from analysis_runs
    where id = target_analysis_run_id
      and status = 'completed'
    for update;

    if target_snapshot_id is null then
        raise exception 'analysis_run % must be completed before publication', target_analysis_run_id;
    end if;

    perform 1
    from corpus_snapshots
    where id = target_snapshot_id
    for share;

    if not found then
        raise exception 'snapshot % does not exist', target_snapshot_id;
    end if;

    select count(*)
    into completed_stage_count
    from analysis_stage_runs
    where analysis_run_id = target_analysis_run_id
      and status = 'completed'
      and result_payload is not null
      and stage in ('thematic_landscape', 'regulatory_intelligence', 'strategic_assessment');

    if completed_stage_count <> 3 then
        raise exception 'analysis_run % must have exactly three completed stages with payload', target_analysis_run_id;
    end if;

    update dashboard_publications
    set is_current = false
    where is_current = true;

    insert into dashboard_publications (
        analysis_run_id,
        snapshot_id,
        published_at,
        is_current
    )
    values (
        target_analysis_run_id,
        target_snapshot_id,
        now(),
        true
    )
    returning id into publication_id;

    update analysis_runs
    set status = 'published',
        published_at = now(),
        error_message = null
    where id = target_analysis_run_id;

    return publication_id;
end;
$$;

create view current_dashboard_publication as
select
    publication.id as publication_id,
    publication.analysis_run_id,
    publication.snapshot_id,
    publication.published_at,
    run.status as analysis_run_status
from dashboard_publications publication
join analysis_runs run on run.id = publication.analysis_run_id
where publication.is_current = true;

alter table corpus_snapshots enable row level security;
alter table corpus_snapshot_documents enable row level security;
alter table corpus_snapshot_record_refs enable row level security;
alter table analysis_runs enable row level security;
alter table analysis_stage_runs enable row level security;
alter table dashboard_publications enable row level security;

commit;
