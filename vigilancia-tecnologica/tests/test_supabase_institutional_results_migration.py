from __future__ import annotations

import re
from pathlib import Path


MIGRATION_0002 = Path("supabase/migrations/0002_individual_results.sql")
MIGRATION_0003 = Path("supabase/migrations/0003_institutional_results.sql")


TABLES = (
    "pmge_projects",
    "pmge_objectives",
    "pmge_activities",
    "regulatory_agenda_initiatives",
    "regulatory_deliverables",
    "policies",
    "policy_activities",
    "policy_commitments",
)


def _sql() -> str:
    return MIGRATION_0003.read_text(encoding="utf-8")


def _table_block(sql: str, table_name: str) -> str:
    pattern = rf"create\s+table\s+{table_name}\s*\((.*?)\);"
    match = re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)
    assert match, f"No se encontro tabla {table_name}"
    return match.group(1).lower()


def test_migration_order_after_0002():
    assert MIGRATION_0002.exists()
    assert MIGRATION_0003.exists()
    assert MIGRATION_0002.name < MIGRATION_0003.name


def test_eight_institutional_child_tables_exist():
    sql = _sql().lower()

    for table_name in TABLES:
        assert f"create table {table_name}" in sql
        assert (
            "id uuid primary key references result_records(id) on delete restrict"
            in _table_block(sql, table_name)
        )


def test_child_tables_do_not_duplicate_common_metadata():
    sql = _sql()
    forbidden = (
        "data jsonb",
        "prompt_id",
        "prompt_version",
        "contract_name",
        "model_name",
        "canonical_key",
        "content_hash",
        "record_version",
        "created_at",
    )

    for table_name in TABLES:
        block = _table_block(sql, table_name)
        for fragment in forbidden:
            assert fragment not in block


def test_pmge_columns_and_relations_match_current_contracts():
    sql = _sql()
    projects = _table_block(sql, "pmge_projects")
    objectives = _table_block(sql, "pmge_objectives")
    activities = _table_block(sql, "pmge_activities")

    for column in (
        "project_name text not null",
        "description text not null",
        "objectives text[] not null default '{}'",
        "activities text[] not null default '{}'",
        "expected_outputs text[] not null default '{}'",
        "period text",
        "responsible_area text",
    ):
        assert column in projects

    assert "project_id uuid references pmge_projects(id) on delete restrict" in objectives
    assert "objective_text text not null" in objectives
    assert "project_id uuid references pmge_projects(id) on delete restrict" in activities
    assert "objective_id uuid references pmge_objectives(id) on delete restrict" in activities
    assert "activity_name text not null" in activities
    assert "activity_description text not null" in activities
    assert "responsible_area text" in activities
    assert "period text" in activities


def test_agenda_columns_and_relations_match_current_contracts():
    sql = _sql()
    initiatives = _table_block(sql, "regulatory_agenda_initiatives")
    deliverables = _table_block(sql, "regulatory_deliverables")

    assert "initiative_name text not null" in initiatives
    assert "regulatory_objective text not null" in initiatives
    assert "deliverables text[] not null default '{}'" in initiatives
    assert "period text" in initiatives
    assert "responsible_area text" in initiatives
    assert (
        "initiative_id uuid not null references regulatory_agenda_initiatives(id) on delete restrict"
        in deliverables
    )
    assert "deliverable_name text not null" in deliverables
    assert "description text" in deliverables
    assert "period text" in deliverables


def test_policy_matrix_columns_and_relations_match_current_contracts():
    sql = _sql()
    policies = _table_block(sql, "policies")
    activities = _table_block(sql, "policy_activities")
    commitments = _table_block(sql, "policy_commitments")

    assert "policy_name text not null" in policies
    assert "instrument_name text" in policies
    assert "policy_axis text" in policies
    assert "description text" in policies
    assert "policy_id uuid references policies(id) on delete restrict" in activities
    assert "activity_name text not null" in activities
    assert "activity_description text not null" in activities
    assert "responsible_area text" in activities
    assert "execution_period text" in activities
    assert "commitments text[] not null default '{}'" in activities
    assert "keywords text[] not null default '{}'" in activities
    assert (
        "policy_activity_id uuid references policy_activities(id) on delete restrict"
        in commitments
    )
    assert "commitment_text text not null" in commitments
    assert "responsible_area text" in commitments
    assert "period text" in commitments


def test_record_type_validation_for_every_child_table():
    sql = _sql().lower()
    expected = {
        "pmge_projects": "pmge_project",
        "pmge_objectives": "pmge_objective",
        "pmge_activities": "pmge_activity",
        "regulatory_agenda_initiatives": "agenda_initiative",
        "regulatory_deliverables": "agenda_deliverable",
        "policies": "policy",
        "policy_activities": "policy_activity",
        "policy_commitments": "policy_commitment",
    }

    for table_name, record_type in expected.items():
        assert f"validate_{table_name}_record_type" in sql
        assert f"perform validate_result_record_type('{record_type}', new.id)" in sql
        assert f"{table_name}_validate_record_type" in sql


def test_cross_document_relation_validation_exists():
    sql = _sql().lower()

    assert "create or replace function validate_same_result_document" in sql
    for relation in (
        "perform validate_same_result_document(new.id, new.project_id)",
        "perform validate_same_result_document(new.id, new.objective_id)",
        "perform validate_same_result_document(new.id, new.initiative_id)",
        "perform validate_same_result_document(new.id, new.policy_id)",
        "perform validate_same_result_document(new.id, new.policy_activity_id)",
    ):
        assert relation in sql
    assert "source_document_id <> related_document_id" in sql


def test_required_text_constraints_exist():
    sql = _sql().lower()

    for fragment in (
        "pmge_projects_name_not_blank",
        "pmge_objectives_text_not_blank",
        "pmge_activities_name_not_blank",
        "pmge_activities_description_not_blank",
        "regulatory_agenda_initiatives_name_not_blank",
        "regulatory_agenda_initiatives_objective_not_blank",
        "regulatory_deliverables_name_not_blank",
        "policies_name_not_blank",
        "policy_activities_name_not_blank",
        "policy_activities_description_not_blank",
        "policy_commitments_text_not_blank",
    ):
        assert fragment in sql


def test_evidence_relation_is_reused_not_recreated():
    sql = _sql().lower()

    assert "result_record_evidence" in sql
    assert "create table result_record_evidence" not in sql
    for forbidden in (
        "pmge_project_evidence",
        "pmge_objective_evidence",
        "pmge_activity_evidence",
        "regulatory_deliverable_evidence",
        "policy_activity_evidence",
        "policy_commitment_evidence",
    ):
        assert forbidden not in sql


def test_indexes_cover_relationships_and_query_names():
    sql = _sql().lower()

    for fragment in (
        "pmge_objectives_project_idx",
        "pmge_activities_project_idx",
        "pmge_activities_objective_idx",
        "pmge_projects_name_idx",
        "regulatory_deliverables_initiative_idx",
        "regulatory_agenda_initiatives_name_idx",
        "policies_name_idx",
        "policy_activities_policy_idx",
        "policy_activities_name_idx",
        "policy_commitments_activity_idx",
    ):
        assert fragment in sql


def test_foreign_keys_are_conservative():
    sql = _sql().lower()

    assert "references result_records(id) on delete restrict" in sql
    assert "references pmge_projects(id) on delete restrict" in sql
    assert "references regulatory_agenda_initiatives(id) on delete restrict" in sql
    assert "references policies(id) on delete restrict" in sql
    assert "on delete cascade" not in sql


def test_rls_enabled_without_policies_or_grants():
    sql = _sql().lower()

    for table_name in TABLES:
        assert f"alter table {table_name} enable row level security" in sql
    assert "create policy" not in sql
    assert "grant " not in sql


def test_no_credentials_or_remote_operations():
    sql = _sql().lower()

    for token in (
        "service_role",
        "anon key",
        "supabase_url",
        "supabase_key",
        "eyjh",
        "postgres://",
        "postgresql://",
    ):
        assert token not in sql


def test_no_snapshots_runs_or_publication_tables_yet():
    sql = _sql().lower()

    for table_name in (
        "corpus_snapshots",
        "corpus_snapshot_record_refs",
        "analysis_runs",
        "analysis_stage_runs",
        "dashboard_publications",
    ):
        assert f"create table {table_name}" not in sql


def test_no_destructive_sql():
    sql = _sql().lower()

    destructive_patterns = (
        r"\bdrop\s+(table|type|schema|database|function|trigger|index)\b",
        r"\btruncate\s+table\b",
        r"\bdelete\s+from\b",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None


def test_migration_is_wrapped_in_transaction():
    statements = [
        line.strip().lower()
        for line in _sql().splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]

    assert statements[0] == "begin;"
    assert statements[-1] == "commit;"
