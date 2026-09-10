-- RPC transaccional para persistir bundles completos de resultados.
-- PostgreSQL ejecuta la funcion en una sola transaccion: si una insercion
-- falla, no quedan registros padre/hijos parciales.

begin;

create or replace function jsonb_text_array(value jsonb)
returns text[]
language sql
immutable
as $$
    select coalesce(array_agg(element), '{}'::text[])
    from jsonb_array_elements_text(coalesce(value, '[]'::jsonb)) as element;
$$;

create or replace function persist_result_bundle(bundle jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    parent_record jsonb;
    child_record jsonb;
    child_table text;
    child_data jsonb;
    evidence_link jsonb;
    target_document_id uuid;
begin
    target_document_id := (bundle->>'document_id')::uuid;

    if exists (
        select 1 from result_records where document_id = target_document_id
    ) then
        raise exception 'result bundle already exists for document %', target_document_id
            using errcode = '23505';
    end if;

    for parent_record in
        select value from jsonb_array_elements(bundle->'result_records')
    loop
        insert into result_records (
            id,
            document_id,
            record_type,
            data,
            prompt_id,
            prompt_version,
            contract_name,
            model_name,
            canonical_key,
            confidence,
            extraction_basis,
            content_hash,
            record_version,
            created_at
        )
        values (
            (parent_record->>'id')::uuid,
            (parent_record->>'document_id')::uuid,
            (parent_record->>'record_type')::result_record_type,
            parent_record->'data',
            parent_record->>'prompt_id',
            parent_record->>'prompt_version',
            parent_record->>'contract_name',
            parent_record->>'model_name',
            parent_record->>'canonical_key',
            nullif(parent_record->>'confidence', '')::confidence_level,
            nullif(parent_record->>'extraction_basis', '')::extraction_basis,
            parent_record->>'content_hash',
            parent_record->>'record_version',
            (parent_record->>'created_at')::timestamptz
        );
    end loop;

    for child_record in
        select value from jsonb_array_elements(bundle->'child_records')
    loop
        child_table := child_record->>'table';
        child_data := child_record->'data';

        case child_table
            when 'document_analysis' then
                insert into document_analysis (
                    id,
                    document_type,
                    title,
                    summary,
                    publication_date,
                    document_date,
                    language,
                    preliminary_topics,
                    technologies,
                    frequency_bands,
                    countries_regions,
                    organizations,
                    actors,
                    keywords
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'document_type',
                    child_data->>'title',
                    child_data->>'summary',
                    child_data->>'publication_date',
                    child_data->>'document_date',
                    child_data->>'language',
                    jsonb_text_array(child_data->'preliminary_topics'),
                    jsonb_text_array(child_data->'technologies'),
                    jsonb_text_array(child_data->'frequency_bands'),
                    jsonb_text_array(child_data->'countries_regions'),
                    jsonb_text_array(child_data->'organizations'),
                    jsonb_text_array(child_data->'actors'),
                    jsonb_text_array(child_data->'keywords')
                );
            when 'findings' then
                insert into findings (
                    id,
                    finding_type,
                    title,
                    description,
                    preliminary_topics,
                    technologies,
                    frequency_bands,
                    countries_regions,
                    organizations
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'finding_type',
                    child_data->>'title',
                    child_data->>'description',
                    jsonb_text_array(child_data->'preliminary_topics'),
                    jsonb_text_array(child_data->'technologies'),
                    jsonb_text_array(child_data->'frequency_bands'),
                    jsonb_text_array(child_data->'countries_regions'),
                    jsonb_text_array(child_data->'organizations')
                );
            when 'evidence' then
                insert into evidence (
                    id,
                    quote,
                    evidence_type,
                    page_number,
                    sheet_name,
                    row_reference,
                    section_title,
                    matched_chunk_id
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'quote',
                    child_data->>'evidence_type',
                    nullif(child_data->>'page_number', '')::integer,
                    child_data->>'sheet_name',
                    child_data->>'row_reference',
                    child_data->>'section_title',
                    nullif(child_data->>'matched_chunk_id', '')::uuid
                );
            when 'pmge_projects' then
                insert into pmge_projects (
                    id,
                    project_name,
                    description,
                    objectives,
                    activities,
                    expected_outputs,
                    period,
                    responsible_area
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'project_name',
                    child_data->>'description',
                    jsonb_text_array(child_data->'objectives'),
                    jsonb_text_array(child_data->'activities'),
                    jsonb_text_array(child_data->'expected_outputs'),
                    child_data->>'period',
                    child_data->>'responsible_area'
                );
            when 'pmge_objectives' then
                insert into pmge_objectives (
                    id,
                    project_id,
                    objective_text
                )
                values (
                    (child_data->>'id')::uuid,
                    nullif(child_data->>'project_id', '')::uuid,
                    child_data->>'objective_text'
                );
            when 'pmge_activities' then
                insert into pmge_activities (
                    id,
                    project_id,
                    objective_id,
                    activity_name,
                    activity_description,
                    responsible_area,
                    period
                )
                values (
                    (child_data->>'id')::uuid,
                    nullif(child_data->>'project_id', '')::uuid,
                    nullif(child_data->>'objective_id', '')::uuid,
                    child_data->>'activity_name',
                    child_data->>'activity_description',
                    child_data->>'responsible_area',
                    child_data->>'period'
                );
            when 'regulatory_agenda_initiatives' then
                insert into regulatory_agenda_initiatives (
                    id,
                    initiative_name,
                    regulatory_objective,
                    deliverables,
                    period,
                    responsible_area
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'initiative_name',
                    child_data->>'regulatory_objective',
                    jsonb_text_array(child_data->'deliverables'),
                    child_data->>'period',
                    child_data->>'responsible_area'
                );
            when 'regulatory_deliverables' then
                insert into regulatory_deliverables (
                    id,
                    initiative_id,
                    deliverable_name,
                    description,
                    period
                )
                values (
                    (child_data->>'id')::uuid,
                    (child_data->>'initiative_id')::uuid,
                    child_data->>'deliverable_name',
                    child_data->>'description',
                    child_data->>'period'
                );
            when 'policies' then
                insert into policies (
                    id,
                    policy_name,
                    instrument_name,
                    policy_axis,
                    description
                )
                values (
                    (child_data->>'id')::uuid,
                    child_data->>'policy_name',
                    child_data->>'instrument_name',
                    child_data->>'policy_axis',
                    child_data->>'description'
                );
            when 'policy_activities' then
                insert into policy_activities (
                    id,
                    policy_id,
                    activity_name,
                    activity_description,
                    responsible_area,
                    execution_period,
                    commitments,
                    keywords
                )
                values (
                    (child_data->>'id')::uuid,
                    nullif(child_data->>'policy_id', '')::uuid,
                    child_data->>'activity_name',
                    child_data->>'activity_description',
                    child_data->>'responsible_area',
                    child_data->>'execution_period',
                    jsonb_text_array(child_data->'commitments'),
                    jsonb_text_array(child_data->'keywords')
                );
            when 'policy_commitments' then
                insert into policy_commitments (
                    id,
                    policy_activity_id,
                    commitment_text,
                    responsible_area,
                    period
                )
                values (
                    (child_data->>'id')::uuid,
                    nullif(child_data->>'policy_activity_id', '')::uuid,
                    child_data->>'commitment_text',
                    child_data->>'responsible_area',
                    child_data->>'period'
                );
            else
                raise exception 'unsupported child result table: %', child_table;
        end case;
    end loop;

    for evidence_link in
        select value from jsonb_array_elements(coalesce(bundle->'evidence_links', '[]'::jsonb))
    loop
        insert into result_record_evidence (
            record_id,
            evidence_id
        )
        values (
            (evidence_link->>'record_id')::uuid,
            (evidence_link->>'evidence_id')::uuid
        );
    end loop;
end;
$$;

commit;
