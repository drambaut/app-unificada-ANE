-- Politicas RLS y grants para la arquitectura escalable.
-- Convencion de roles de aplicacion en JWT:
--   app_metadata.role = 'admin' | 'analyst' | 'reader'
--
-- El backend y los jobs administrativos deben usar service_role. Los clientes
-- anonimos solo pueden leer la publicacion vigente del dashboard.

begin;

create or replace function app_jwt_role()
returns text
language sql
stable
as $$
    select coalesce(
        nullif(auth.jwt() -> 'app_metadata' ->> 'role', ''),
        nullif(auth.jwt() -> 'user_metadata' ->> 'role', ''),
        'anonymous'
    );
$$;

create or replace function app_has_role(allowed_roles text[])
returns boolean
language sql
stable
as $$
    select app_jwt_role() = any(allowed_roles);
$$;

create or replace function app_can_manage_corpus()
returns boolean
language sql
stable
as $$
    select app_has_role(array['admin', 'analyst']);
$$;

create or replace function app_can_read_internal()
returns boolean
language sql
stable
as $$
    select app_has_role(array['admin', 'analyst']);
$$;

create or replace function app_can_read_dashboard()
returns boolean
language sql
stable
as $$
    select app_has_role(array['admin', 'analyst', 'reader']);
$$;

grant usage on schema public to anon, authenticated;
grant select on current_dashboard_publication to anon, authenticated;

grant select on
    documents,
    result_records,
    corpus_snapshots,
    corpus_snapshot_documents,
    corpus_snapshot_record_refs,
    analysis_runs,
    analysis_stage_runs,
    dashboard_publications
to anon, authenticated;

grant select on
    document_chunks,
    processing_jobs,
    document_analysis,
    findings,
    evidence,
    result_record_evidence,
    pmge_projects,
    pmge_objectives,
    pmge_activities,
    regulatory_agenda_initiatives,
    regulatory_deliverables,
    policies,
    policy_activities,
    policy_commitments
to authenticated;

grant insert, update on
    documents,
    document_chunks,
    processing_jobs,
    result_records,
    document_analysis,
    findings,
    evidence,
    result_record_evidence,
    pmge_projects,
    pmge_objectives,
    pmge_activities,
    regulatory_agenda_initiatives,
    regulatory_deliverables,
    policies,
    policy_activities,
    policy_commitments,
    corpus_snapshots,
    corpus_snapshot_documents,
    corpus_snapshot_record_refs,
    analysis_runs,
    analysis_stage_runs,
    dashboard_publications
to authenticated;

revoke execute on function persist_result_bundle(jsonb) from public, anon, authenticated;
grant execute on function persist_result_bundle(jsonb) to service_role;

revoke execute on function publish_analysis_run(uuid) from public, anon, authenticated;
grant execute on function publish_analysis_run(uuid) to service_role;

create policy documents_read_current_publication
on documents
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from corpus_snapshot_documents snapshot_document
        join dashboard_publications publication
            on publication.snapshot_id = snapshot_document.snapshot_id
        where publication.is_current = true
          and snapshot_document.document_id = documents.id
    )
);

create policy documents_manage_authenticated
on documents
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy document_chunks_read_internal
on document_chunks
for select
to authenticated
using (app_can_read_internal());

create policy document_chunks_manage_authenticated
on document_chunks
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy processing_jobs_read_internal
on processing_jobs
for select
to authenticated
using (app_can_read_internal());

create policy processing_jobs_manage_authenticated
on processing_jobs
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy result_records_read_current_publication
on result_records
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from corpus_snapshot_record_refs snapshot_ref
        join dashboard_publications publication
            on publication.snapshot_id = snapshot_ref.snapshot_id
        where publication.is_current = true
          and snapshot_ref.record_id = result_records.id
    )
);

create policy result_records_manage_authenticated
on result_records
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy document_analysis_read_internal on document_analysis
for select to authenticated using (app_can_read_internal());
create policy findings_read_internal on findings
for select to authenticated using (app_can_read_internal());
create policy evidence_read_internal on evidence
for select to authenticated using (app_can_read_internal());
create policy result_record_evidence_read_internal on result_record_evidence
for select to authenticated using (app_can_read_internal());
create policy pmge_projects_read_internal on pmge_projects
for select to authenticated using (app_can_read_internal());
create policy pmge_objectives_read_internal on pmge_objectives
for select to authenticated using (app_can_read_internal());
create policy pmge_activities_read_internal on pmge_activities
for select to authenticated using (app_can_read_internal());
create policy regulatory_agenda_initiatives_read_internal on regulatory_agenda_initiatives
for select to authenticated using (app_can_read_internal());
create policy regulatory_deliverables_read_internal on regulatory_deliverables
for select to authenticated using (app_can_read_internal());
create policy policies_read_internal on policies
for select to authenticated using (app_can_read_internal());
create policy policy_activities_read_internal on policy_activities
for select to authenticated using (app_can_read_internal());
create policy policy_commitments_read_internal on policy_commitments
for select to authenticated using (app_can_read_internal());

create policy document_analysis_manage_authenticated on document_analysis
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy findings_manage_authenticated on findings
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy evidence_manage_authenticated on evidence
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy result_record_evidence_manage_authenticated on result_record_evidence
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy pmge_projects_manage_authenticated on pmge_projects
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy pmge_objectives_manage_authenticated on pmge_objectives
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy pmge_activities_manage_authenticated on pmge_activities
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy regulatory_agenda_initiatives_manage_authenticated on regulatory_agenda_initiatives
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy regulatory_deliverables_manage_authenticated on regulatory_deliverables
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy policies_manage_authenticated on policies
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy policy_activities_manage_authenticated on policy_activities
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());
create policy policy_commitments_manage_authenticated on policy_commitments
for all to authenticated using (app_can_manage_corpus()) with check (app_can_manage_corpus());

create policy corpus_snapshots_read_current_publication
on corpus_snapshots
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from dashboard_publications publication
        where publication.is_current = true
          and publication.snapshot_id = corpus_snapshots.id
    )
);

create policy corpus_snapshots_manage_authenticated
on corpus_snapshots
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy corpus_snapshot_documents_read_current_publication
on corpus_snapshot_documents
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from dashboard_publications publication
        where publication.is_current = true
          and publication.snapshot_id = corpus_snapshot_documents.snapshot_id
    )
);

create policy corpus_snapshot_documents_manage_authenticated
on corpus_snapshot_documents
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy corpus_snapshot_record_refs_read_current_publication
on corpus_snapshot_record_refs
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from dashboard_publications publication
        where publication.is_current = true
          and publication.snapshot_id = corpus_snapshot_record_refs.snapshot_id
    )
);

create policy corpus_snapshot_record_refs_manage_authenticated
on corpus_snapshot_record_refs
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy analysis_runs_read_current_publication
on analysis_runs
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from dashboard_publications publication
        where publication.is_current = true
          and publication.analysis_run_id = analysis_runs.id
    )
);

create policy analysis_runs_manage_authenticated
on analysis_runs
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy analysis_stage_runs_read_current_publication
on analysis_stage_runs
for select
to anon, authenticated
using (
    app_can_read_dashboard()
    or exists (
        select 1
        from dashboard_publications publication
        where publication.is_current = true
          and publication.analysis_run_id = analysis_stage_runs.analysis_run_id
    )
);

create policy analysis_stage_runs_manage_authenticated
on analysis_stage_runs
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy dashboard_publications_read_current
on dashboard_publications
for select
to anon, authenticated
using (
    is_current = true
    or app_can_read_dashboard()
);

create policy dashboard_publications_manage_authenticated
on dashboard_publications
for all
to authenticated
using (app_can_manage_corpus())
with check (app_can_manage_corpus());

create policy source_documents_read_authenticated
on storage.objects
for select
to authenticated
using (
    bucket_id = 'source-documents'
    and app_can_read_internal()
);

create policy source_documents_insert_authenticated
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'source-documents'
    and app_can_manage_corpus()
);

create policy source_documents_update_authenticated
on storage.objects
for update
to authenticated
using (
    bucket_id = 'source-documents'
    and app_can_manage_corpus()
)
with check (
    bucket_id = 'source-documents'
    and app_can_manage_corpus()
);

create policy source_documents_delete_authenticated
on storage.objects
for delete
to authenticated
using (
    bucket_id = 'source-documents'
    and app_can_manage_corpus()
);

commit;
