-- Resultados institucionales normalizados.
-- Debe ejecutarse despues de 0001_documents_and_jobs.sql y
-- 0002_individual_results.sql.
-- Las entidades son append-only y reutilizan result_records como tabla padre.
-- La evidencia se relaciona mediante result_record_evidence; no se crean
-- tablas de evidencia especificas por entidad.

begin;

create table pmge_projects (
    id uuid primary key references result_records(id) on delete restrict,
    project_name text not null,
    description text not null,
    objectives text[] not null default '{}',
    activities text[] not null default '{}',
    expected_outputs text[] not null default '{}',
    period text,
    responsible_area text,
    constraint pmge_projects_name_not_blank check (length(btrim(project_name)) > 0)
);

create table pmge_objectives (
    id uuid primary key references result_records(id) on delete restrict,
    project_id uuid references pmge_projects(id) on delete restrict,
    objective_text text not null,
    constraint pmge_objectives_text_not_blank check (length(btrim(objective_text)) > 0)
);

create table pmge_activities (
    id uuid primary key references result_records(id) on delete restrict,
    project_id uuid references pmge_projects(id) on delete restrict,
    objective_id uuid references pmge_objectives(id) on delete restrict,
    activity_name text not null,
    activity_description text not null,
    responsible_area text,
    period text,
    constraint pmge_activities_name_not_blank check (length(btrim(activity_name)) > 0),
    constraint pmge_activities_description_not_blank check (length(btrim(activity_description)) > 0)
);

create table regulatory_agenda_initiatives (
    id uuid primary key references result_records(id) on delete restrict,
    initiative_name text not null,
    regulatory_objective text not null,
    deliverables text[] not null default '{}',
    period text,
    responsible_area text,
    constraint regulatory_agenda_initiatives_name_not_blank check (length(btrim(initiative_name)) > 0),
    constraint regulatory_agenda_initiatives_objective_not_blank check (length(btrim(regulatory_objective)) > 0)
);

create table regulatory_deliverables (
    id uuid primary key references result_records(id) on delete restrict,
    initiative_id uuid not null references regulatory_agenda_initiatives(id) on delete restrict,
    deliverable_name text not null,
    description text,
    period text,
    constraint regulatory_deliverables_name_not_blank check (length(btrim(deliverable_name)) > 0)
);

create table policies (
    id uuid primary key references result_records(id) on delete restrict,
    policy_name text not null,
    instrument_name text,
    policy_axis text,
    description text,
    constraint policies_name_not_blank check (length(btrim(policy_name)) > 0)
);

create table policy_activities (
    id uuid primary key references result_records(id) on delete restrict,
    policy_id uuid references policies(id) on delete restrict,
    activity_name text not null,
    activity_description text not null,
    responsible_area text,
    execution_period text,
    commitments text[] not null default '{}',
    keywords text[] not null default '{}',
    constraint policy_activities_name_not_blank check (length(btrim(activity_name)) > 0),
    constraint policy_activities_description_not_blank check (length(btrim(activity_description)) > 0)
);

create table policy_commitments (
    id uuid primary key references result_records(id) on delete restrict,
    policy_activity_id uuid references policy_activities(id) on delete restrict,
    commitment_text text not null,
    responsible_area text,
    period text,
    constraint policy_commitments_text_not_blank check (length(btrim(commitment_text)) > 0)
);

create or replace function validate_same_result_document(
    source_record_id uuid,
    related_record_id uuid
)
returns void
language plpgsql
as $$
declare
    source_document_id uuid;
    related_document_id uuid;
begin
    if related_record_id is null then
        return;
    end if;

    select document_id into source_document_id
    from result_records
    where id = source_record_id;

    select document_id into related_document_id
    from result_records
    where id = related_record_id;

    if source_document_id is null or related_document_id is null then
        raise exception 'result_record relation references missing record';
    end if;

    if source_document_id <> related_document_id then
        raise exception 'result_record relation crosses documents: % -> %',
            source_record_id,
            related_record_id;
    end if;
end;
$$;

create or replace function validate_pmge_projects_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('pmge_project', new.id);
    return new;
end;
$$;

create or replace function validate_pmge_objectives_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('pmge_objective', new.id);
    perform validate_same_result_document(new.id, new.project_id);
    return new;
end;
$$;

create or replace function validate_pmge_activities_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('pmge_activity', new.id);
    perform validate_same_result_document(new.id, new.project_id);
    perform validate_same_result_document(new.id, new.objective_id);
    return new;
end;
$$;

create or replace function validate_regulatory_agenda_initiatives_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('agenda_initiative', new.id);
    return new;
end;
$$;

create or replace function validate_regulatory_deliverables_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('agenda_deliverable', new.id);
    perform validate_same_result_document(new.id, new.initiative_id);
    return new;
end;
$$;

create or replace function validate_policies_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('policy', new.id);
    return new;
end;
$$;

create or replace function validate_policy_activities_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('policy_activity', new.id);
    perform validate_same_result_document(new.id, new.policy_id);
    return new;
end;
$$;

create or replace function validate_policy_commitments_record_type()
returns trigger
language plpgsql
as $$
begin
    perform validate_result_record_type('policy_commitment', new.id);
    perform validate_same_result_document(new.id, new.policy_activity_id);
    return new;
end;
$$;

create trigger pmge_projects_validate_record_type
before insert on pmge_projects
for each row
execute function validate_pmge_projects_record_type();

create trigger pmge_objectives_validate_record_type
before insert on pmge_objectives
for each row
execute function validate_pmge_objectives_record_type();

create trigger pmge_activities_validate_record_type
before insert on pmge_activities
for each row
execute function validate_pmge_activities_record_type();

create trigger regulatory_agenda_initiatives_validate_record_type
before insert on regulatory_agenda_initiatives
for each row
execute function validate_regulatory_agenda_initiatives_record_type();

create trigger regulatory_deliverables_validate_record_type
before insert on regulatory_deliverables
for each row
execute function validate_regulatory_deliverables_record_type();

create trigger policies_validate_record_type
before insert on policies
for each row
execute function validate_policies_record_type();

create trigger policy_activities_validate_record_type
before insert on policy_activities
for each row
execute function validate_policy_activities_record_type();

create trigger policy_commitments_validate_record_type
before insert on policy_commitments
for each row
execute function validate_policy_commitments_record_type();

create index pmge_objectives_project_idx
    on pmge_objectives (project_id)
    where project_id is not null;

create index pmge_activities_project_idx
    on pmge_activities (project_id)
    where project_id is not null;

create index pmge_activities_objective_idx
    on pmge_activities (objective_id)
    where objective_id is not null;

create index pmge_projects_name_idx
    on pmge_projects (project_name);

create index regulatory_deliverables_initiative_idx
    on regulatory_deliverables (initiative_id);

create index regulatory_agenda_initiatives_name_idx
    on regulatory_agenda_initiatives (initiative_name);

create index policies_name_idx
    on policies (policy_name);

create index policy_activities_policy_idx
    on policy_activities (policy_id)
    where policy_id is not null;

create index policy_activities_name_idx
    on policy_activities (activity_name);

create index policy_commitments_activity_idx
    on policy_commitments (policy_activity_id)
    where policy_activity_id is not null;

alter table pmge_projects enable row level security;
alter table pmge_objectives enable row level security;
alter table pmge_activities enable row level security;
alter table regulatory_agenda_initiatives enable row level security;
alter table regulatory_deliverables enable row level security;
alter table policies enable row level security;
alter table policy_activities enable row level security;
alter table policy_commitments enable row level security;

commit;
