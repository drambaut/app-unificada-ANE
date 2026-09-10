from __future__ import annotations

import re
from pathlib import Path

from app.analysis_runs.models import AnalysisRunStatus, AnalysisStage


MIGRATION_0003 = Path("supabase/migrations/0003_institutional_results.sql")
MIGRATION_0004 = Path("supabase/migrations/0004_snapshots_analysis_and_publication.sql")


def _sql() -> str:
    return MIGRATION_0004.read_text(encoding="utf-8")


def _enum_values(sql: str, enum_name: str) -> list[str]:
    pattern = rf"create\s+type\s+{enum_name}\s+as\s+enum\s*\((.*?)\);"
    match = re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)
    assert match, f"No se encontro enum {enum_name}"
    return re.findall(r"'([^']+)'", match.group(1))


def _table_block(sql: str, table_name: str) -> str:
    pattern = rf"create\s+table\s+{table_name}\s*\((.*?)\);"
    match = re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)
    assert match, f"No se encontro tabla {table_name}"
    return match.group(1).lower()


def test_migration_order_after_0003():
    assert MIGRATION_0003.exists()
    assert MIGRATION_0004.exists()
    assert MIGRATION_0003.name < MIGRATION_0004.name


def test_enums_match_domain_and_stage_has_no_published():
    sql = _sql()

    assert _enum_values(sql, "analysis_run_status") == [
        item.value for item in AnalysisRunStatus
    ]
    assert _enum_values(sql, "analysis_stage") == [item.value for item in AnalysisStage]
    assert _enum_values(sql, "analysis_stage_status") == [
        "queued",
        "running",
        "completed",
        "failed",
    ]
    assert "published" not in _enum_values(sql, "analysis_stage_status")


def test_required_tables_exist():
    sql = _sql().lower()

    for table_name in (
        "corpus_snapshots",
        "corpus_snapshot_documents",
        "corpus_snapshot_record_refs",
        "analysis_runs",
        "analysis_stage_runs",
        "dashboard_publications",
    ):
        assert f"create table {table_name}" in sql


def test_corpus_snapshots_are_append_only_shape():
    block = _table_block(_sql(), "corpus_snapshots")

    for column in (
        "id uuid primary key",
        "created_at timestamptz not null",
        "snapshot_hash text not null",
        "selection_criteria jsonb not null",
        "metadata jsonb not null",
        "corpus_snapshots_snapshot_hash_unique unique (snapshot_hash)",
        "jsonb_typeof(selection_criteria) = 'object'",
        "jsonb_typeof(metadata) = 'object'",
    ):
        assert column in block


def test_snapshot_documents_and_refs_have_conservative_fks():
    sql = _sql()
    documents = _table_block(sql, "corpus_snapshot_documents")
    refs = _table_block(sql, "corpus_snapshot_record_refs")

    assert "snapshot_id uuid not null references corpus_snapshots(id) on delete restrict" in documents
    assert "document_id uuid not null references documents(id) on delete restrict" in documents
    assert "source_type source_type not null" in documents
    assert "primary key (snapshot_id, document_id)" in documents

    assert "snapshot_id uuid not null references corpus_snapshots(id) on delete restrict" in refs
    assert "record_id uuid not null references result_records(id) on delete restrict" in refs
    assert "document_id uuid not null references documents(id) on delete restrict" in refs
    assert "record_type result_record_type not null" in refs
    assert "canonical_key text not null" in refs
    assert "content_hash text not null" in refs
    assert "record_version text not null" in refs
    assert "created_at timestamptz not null" in refs
    assert "unique (snapshot_id, record_id)" in refs


def test_snapshot_ref_validation_triggers_exist():
    sql = _sql().lower()

    assert "create or replace function validate_snapshot_document_source_type" in sql
    assert "actual_source_type <> new.source_type" in sql
    assert "create or replace function validate_snapshot_record_ref" in sql
    for fragment in (
        "actual_document_id <> new.document_id",
        "actual_record_type <> new.record_type",
        "actual_canonical_key <> new.canonical_key",
        "actual_content_hash <> new.content_hash",
        "actual_record_version <> new.record_version",
        "corpus_snapshot_documents_validate_source_type",
        "corpus_snapshot_record_refs_validate_frozen_values",
    ):
        assert fragment in sql


def test_analysis_runs_align_with_dataclass():
    block = _table_block(_sql(), "analysis_runs")

    for column in (
        "id uuid primary key",
        "corpus_snapshot_id uuid not null references corpus_snapshots(id) on delete restrict",
        "status analysis_run_status not null",
        "attempts integer not null default 0",
        "created_at timestamptz not null",
        "updated_at timestamptz not null",
        "started_at timestamptz",
        "completed_at timestamptz",
        "published_at timestamptz",
        "failed_at timestamptz",
        "error_message text",
        "analysis_runs_attempts_non_negative check (attempts >= 0)",
        "status <> 'published' or published_at is not null",
    ):
        assert column in block


def test_analysis_stage_runs_align_with_dataclass_and_payload_constraints():
    block = _table_block(_sql(), "analysis_stage_runs")

    for column in (
        "id uuid primary key",
        "analysis_run_id uuid not null references analysis_runs(id) on delete restrict",
        "stage analysis_stage not null",
        "status analysis_stage_status not null",
        "prompt_id text not null",
        "prompt_version text not null",
        "contract_name text not null",
        "attempts integer not null default 0",
        "result_payload jsonb",
        "analysis_stage_runs_unique_stage unique (analysis_run_id, stage)",
        "result_payload is null or jsonb_typeof(result_payload) = 'object'",
        "status <> 'completed' or result_payload is not null",
    ):
        assert column in block


def test_concurrent_runs_and_unique_stages_are_constrained():
    sql = _sql().lower()

    assert "analysis_runs_active_snapshot_unique_idx" in sql
    assert "on analysis_runs (corpus_snapshot_id)" in sql
    assert "where status in ('queued', 'running')" in sql
    assert "analysis_stage_runs_unique_stage unique (analysis_run_id, stage)" in sql


def test_dashboard_publications_support_history_and_single_current():
    block = _table_block(_sql(), "dashboard_publications")
    sql = _sql().lower()

    assert "id uuid primary key" in block
    assert "analysis_run_id uuid not null references analysis_runs(id) on delete restrict" in block
    assert "snapshot_id uuid not null references corpus_snapshots(id) on delete restrict" in block
    assert "published_at timestamptz not null" in block
    assert "is_current boolean not null default true" in block
    assert "dashboard_publications_analysis_run_unique unique (analysis_run_id)" in block
    assert "dashboard_publications_current_unique_idx" in sql
    assert "where is_current" in sql


def test_publication_function_is_atomic_and_validates_run_and_stages():
    sql = _sql().lower()

    assert "create or replace function publish_analysis_run(target_analysis_run_id uuid)" in sql
    assert "for update" in sql
    assert "and status = 'completed'" in sql
    assert "for share" in sql
    assert "completed_stage_count <> 3" in sql
    assert "status = 'completed'" in sql
    assert "result_payload is not null" in sql
    assert "update dashboard_publications" in sql
    assert "set is_current = false" in sql
    assert "insert into dashboard_publications" in sql
    assert "update analysis_runs" in sql
    assert "set status = 'published'" in sql
    assert "return publication_id" in sql
    assert "security definer" not in sql


def test_current_dashboard_publication_view_exists():
    sql = _sql().lower()

    assert "create view current_dashboard_publication as" in sql
    assert "from dashboard_publications publication" in sql
    assert "join analysis_runs run on run.id = publication.analysis_run_id" in sql
    assert "where publication.is_current = true" in sql


def test_indexes_exist_without_obvious_redundancy():
    sql = _sql().lower()

    for fragment in (
        "corpus_snapshots_snapshot_hash_idx",
        "corpus_snapshot_record_refs_snapshot_type_idx",
        "corpus_snapshot_record_refs_record_idx",
        "analysis_runs_snapshot_status_idx",
        "analysis_stage_runs_run_stage_idx",
        "dashboard_publications_run_idx",
    ):
        assert fragment in sql


def test_rls_enabled_without_policies_roles_grants_or_credentials():
    sql = _sql().lower()

    for table_name in (
        "corpus_snapshots",
        "corpus_snapshot_documents",
        "corpus_snapshot_record_refs",
        "analysis_runs",
        "analysis_stage_runs",
        "dashboard_publications",
    ):
        assert f"alter table {table_name} enable row level security" in sql
    for token in (
        "create policy",
        "grant ",
        "service_role",
        "anon key",
        "supabase_url",
        "supabase_key",
        "eyjh",
        "postgres://",
        "postgresql://",
    ):
        assert token not in sql


def test_no_destructive_sql_but_publication_updates_are_allowed():
    sql = _sql().lower()

    assert "update dashboard_publications" in sql
    assert "update analysis_runs" in sql
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
