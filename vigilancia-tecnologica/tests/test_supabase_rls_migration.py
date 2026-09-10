from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("supabase/migrations/20260717180000_configure_rls_policies.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_rls_migration_exists_after_schema_and_rpc_migrations():
    assert MIGRATION.exists()
    assert Path("supabase/migrations/20260717165000_persist_result_bundle_rpc.sql").name < MIGRATION.name


def test_application_role_helpers_use_jwt_metadata():
    sql = _sql()

    for fragment in (
        "create or replace function app_jwt_role()",
        "auth.jwt() -> 'app_metadata' ->> 'role'",
        "auth.jwt() -> 'user_metadata' ->> 'role'",
        "create or replace function app_can_manage_corpus()",
        "array['admin', 'analyst']",
        "create or replace function app_can_read_dashboard()",
        "array['admin', 'analyst', 'reader']",
    ):
        assert fragment in sql


def test_sensitive_rpcs_are_service_role_only():
    sql = _sql()

    for function_name in ("persist_result_bundle(jsonb)", "publish_analysis_run(uuid)"):
        assert f"revoke execute on function {function_name} from public, anon, authenticated" in sql
        assert f"grant execute on function {function_name} to service_role" in sql


def test_dashboard_publication_can_be_read_by_anon_with_row_policies():
    sql = _sql()

    for table_name in (
        "documents",
        "result_records",
        "corpus_snapshots",
        "corpus_snapshot_documents",
        "corpus_snapshot_record_refs",
        "analysis_runs",
        "analysis_stage_runs",
        "dashboard_publications",
    ):
        assert f"grant select on" in sql
        assert table_name in sql
        assert f"on {table_name}" in sql
    assert "to anon, authenticated" in sql
    assert "publication.is_current = true" in sql


def test_storage_bucket_policies_are_authenticated_only():
    sql = _sql()

    for operation in ("select", "insert", "update", "delete"):
        assert f"on storage.objects\nfor {operation}\nto authenticated" in sql
    assert "bucket_id = 'source-documents'" in sql
    assert "source_documents_read_authenticated" in sql
    assert "source_documents_insert_authenticated" in sql
    assert "source_documents_update_authenticated" in sql
    assert "source_documents_delete_authenticated" in sql
    assert "to anon" not in _policy_block(sql, "source_documents_read_authenticated")


def test_authenticated_writes_require_admin_or_analyst_role():
    sql = _sql()

    assert "grant insert, update on" in sql
    assert "to authenticated" in sql
    assert "with check (app_can_manage_corpus())" in sql
    assert "for all\nto authenticated\nusing (app_can_manage_corpus())" in sql


def test_no_credentials_or_destructive_sql():
    sql = _sql()

    for token in ("supabase_url", "supabase_key", "eyjh", "postgres://", "postgresql://"):
        assert token not in sql
    for pattern in (
        r"\bdrop\s+(table|type|schema|database|function|trigger|index)\b",
        r"\btruncate\s+table\b",
        r"\bdelete\s+from\b",
    ):
        assert re.search(pattern, sql) is None


def test_migration_is_wrapped_in_transaction():
    statements = [
        line.strip().lower()
        for line in MIGRATION.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]

    assert statements[0] == "begin;"
    assert statements[-1] == "commit;"


def _policy_block(sql: str, policy_name: str) -> str:
    pattern = rf"create policy {policy_name}.*?;"
    match = re.search(pattern, sql, flags=re.DOTALL)
    assert match, f"No se encontro policy {policy_name}"
    return match.group(0)
