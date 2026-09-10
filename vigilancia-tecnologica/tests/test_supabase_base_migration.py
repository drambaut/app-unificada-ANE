from __future__ import annotations

import re
from pathlib import Path

from app.documents.models import DocumentStatus, JobStatus, JobType, SourceType


MIGRATION = Path("supabase/migrations/0001_documents_and_jobs.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _enum_values(sql: str, enum_name: str) -> list[str]:
    pattern = rf"create\s+type\s+{enum_name}\s+as\s+enum\s*\((.*?)\);"
    match = re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)
    assert match, f"No se encontro enum {enum_name}"
    return re.findall(r"'([^']+)'", match.group(1))


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_required_extension_tables_and_enums_exist():
    sql = _sql().lower()

    assert "create extension if not exists pgcrypto" in sql
    for enum_name in ("source_type", "document_status", "job_type", "job_status"):
        assert f"create type {enum_name} as enum" in sql
    for table_name in ("documents", "document_chunks", "processing_jobs"):
        assert f"create table {table_name}" in sql


def test_sql_enum_values_match_python_enums():
    sql = _sql()

    assert _enum_values(sql, "source_type") == [item.value for item in SourceType]
    assert _enum_values(sql, "document_status") == [item.value for item in DocumentStatus]
    assert _enum_values(sql, "job_type") == [item.value for item in JobType]
    assert _enum_values(sql, "job_status") == [item.value for item in JobStatus]


def test_documents_columns_match_current_domain_model():
    sql = _sql().lower()

    for column in (
        "id uuid primary key",
        "file_name text not null",
        "file_type text not null",
        "source_type source_type not null",
        "file_hash text not null",
        "storage_bucket text",
        "storage_path text",
        "document_date date",
        "status document_status not null",
        "version integer not null",
        "replaces_id uuid references documents(id) on delete restrict",
        "created_at timestamptz not null",
        "updated_at timestamptz not null",
    ):
        assert column in sql


def test_document_chunks_columns_match_current_domain_model():
    sql = _sql().lower()

    for column in (
        "id uuid primary key",
        "document_id uuid not null references documents(id) on delete restrict",
        "content text not null",
        "page_number integer",
        "section_title text",
        "sheet_name text",
        "row_reference text",
        "content_hash text not null",
        "position integer not null",
    ):
        assert column in sql


def test_processing_jobs_columns_match_current_domain_model():
    sql = _sql().lower()

    for column in (
        "id uuid primary key",
        "document_id uuid not null references documents(id) on delete restrict",
        "job_type job_type not null",
        "status job_status not null",
        "prompt_id text",
        "prompt_version text",
        "attempts integer not null",
        "error_message text",
        "created_at timestamptz not null",
        "completed_at timestamptz",
    ):
        assert column in sql
    assert "started_at" not in sql


def test_constraints_and_indexes_exist():
    sql = _sql().lower()

    for fragment in (
        "documents_file_hash_unique unique (file_hash)",
        "document_chunks_document_position_unique unique (document_id, position)",
        "page_number is null or page_number > 0",
        "document_chunks_position_non_negative check (position >= 0)",
        "processing_jobs_attempts_non_negative check (attempts >= 0)",
        "documents_source_type_status_idx",
        "processing_jobs_document_status_idx",
        "processing_jobs_type_status_idx",
        "document_chunks_document_page_idx",
        "document_chunks_document_sheet_row_idx",
        "processing_jobs_active_unique_idx",
        "where status in ('queued', 'running')",
    ):
        assert fragment in sql


def test_foreign_keys_are_conservative():
    sql = _sql().lower()

    assert "references documents(id) on delete restrict" in sql
    assert "on delete cascade" not in sql


def test_documents_updated_at_trigger_exists():
    sql = _sql().lower()

    assert "create or replace function set_documents_updated_at()" in sql
    assert "create trigger documents_set_updated_at" in sql
    assert "before update on documents" in sql
    assert "new.updated_at = now();" in sql


def test_rls_enabled_without_policies_or_grants():
    sql = _sql().lower()

    for table_name in ("documents", "document_chunks", "processing_jobs"):
        assert f"alter table {table_name} enable row level security" in sql
    assert "create policy" not in sql
    assert "grant " not in sql


def test_no_credentials_or_remote_supabase_operations():
    sql = _sql().lower()

    forbidden = (
        "service_role",
        "anon key",
        "supabase_url",
        "supabase_key",
        "eyjh",
        "postgres://",
        "postgresql://",
    )
    for token in forbidden:
        assert token not in sql


def test_no_result_tables_yet():
    sql = _sql().lower()

    forbidden_tables = (
        "document_analysis",
        "findings",
        "evidence",
        "pmge_projects",
        "regulatory_agenda_initiatives",
        "policies",
        "corpus_snapshots",
        "analysis_runs",
        "dashboard_publications",
    )
    for table_name in forbidden_tables:
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
