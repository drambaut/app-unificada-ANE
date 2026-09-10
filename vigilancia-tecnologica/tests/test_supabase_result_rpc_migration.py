from __future__ import annotations

from pathlib import Path


MIGRATION = Path("supabase/migrations/20260717165000_persist_result_bundle_rpc.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_result_bundle_rpc_migration_exists_after_result_tables():
    assert MIGRATION.exists()
    assert Path("supabase/migrations/0003_institutional_results.sql").name < MIGRATION.name


def test_persist_result_bundle_rpc_is_transactional_and_backend_only():
    sql = _sql()

    assert "create or replace function persist_result_bundle(bundle jsonb)" in sql
    assert "returns void" in sql
    assert "language plpgsql" in sql
    assert "security definer" in sql
    assert "set search_path = public" in sql
    assert "begin;" in sql
    assert "commit;" in sql
    assert "result bundle already exists for document" in sql


def test_rpc_inserts_parent_children_and_evidence_links():
    sql = _sql()

    for fragment in (
        "insert into result_records",
        "insert into document_analysis",
        "insert into findings",
        "insert into evidence",
        "insert into pmge_projects",
        "insert into pmge_objectives",
        "insert into pmge_activities",
        "insert into regulatory_agenda_initiatives",
        "insert into regulatory_deliverables",
        "insert into policies",
        "insert into policy_activities",
        "insert into policy_commitments",
        "insert into result_record_evidence",
    ):
        assert fragment in sql


def test_rpc_preserves_snapshot_integrity_fields():
    sql = _sql()

    for fragment in (
        "parent_record->>'content_hash'",
        "parent_record->>'record_version'",
        "(parent_record->>'created_at')::timestamptz",
        "(parent_record->>'record_type')::result_record_type",
        "parent_record->'data'",
    ):
        assert fragment in sql


def test_rpc_handles_text_array_fields_without_dynamic_sql():
    sql = _sql()

    assert "create or replace function jsonb_text_array(value jsonb)" in sql
    assert "execute " not in sql
    for field in (
        "preliminary_topics",
        "technologies",
        "frequency_bands",
        "countries_regions",
        "organizations",
        "actors",
        "keywords",
        "objectives",
        "activities",
        "expected_outputs",
        "deliverables",
        "commitments",
    ):
        assert f"jsonb_text_array(child_data->'{field}')" in sql
