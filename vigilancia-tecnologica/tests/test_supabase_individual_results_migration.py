from __future__ import annotations

import re
from pathlib import Path

from app.contracts.common import CONFIDENCE_VALUES, EXTRACTION_BASIS_VALUES
from app.results.models import PersistenceBundle, ResultRecord


MIGRATION_0001 = Path("supabase/migrations/0001_documents_and_jobs.sql")
MIGRATION_0002 = Path("supabase/migrations/0002_individual_results.sql")


def _sql() -> str:
    return MIGRATION_0002.read_text(encoding="utf-8")


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


def test_migration_order_after_0001():
    assert MIGRATION_0001.exists()
    assert MIGRATION_0002.exists()
    assert MIGRATION_0001.name < MIGRATION_0002.name


def test_enums_match_python_contract_values():
    sql = _sql()

    assert _enum_values(sql, "confidence_level") == CONFIDENCE_VALUES
    assert _enum_values(sql, "extraction_basis") == EXTRACTION_BASIS_VALUES


def test_result_record_type_covers_current_persistence_bundle_types():
    sql = _sql()
    values = _enum_values(sql, "result_record_type")
    expected = [
        "document_analysis",
        "finding",
        "evidence",
        "pmge_project",
        "pmge_objective",
        "pmge_activity",
        "agenda_initiative",
        "agenda_deliverable",
        "policy",
        "policy_activity",
        "policy_commitment",
    ]

    assert values == expected
    assert set(PersistenceBundle.__dataclass_fields__) >= {
        "document_analysis",
        "findings",
        "evidence",
        "pmge_projects",
        "pmge_objectives",
        "pmge_activities",
        "regulatory_agenda_initiatives",
        "regulatory_deliverables",
        "policies",
        "policy_activities",
        "policy_commitments",
    }


def test_parent_table_matches_result_record_model():
    sql = _sql().lower()
    block = _table_block(_sql(), "result_records")

    for column in (
        "id uuid primary key",
        "document_id uuid not null references documents(id) on delete restrict",
        "record_type result_record_type not null",
        "data jsonb not null",
        "prompt_id text not null",
        "prompt_version text not null",
        "contract_name text not null",
        "model_name text not null",
        "canonical_key text not null",
        "confidence confidence_level",
        "extraction_basis extraction_basis",
        "content_hash text not null",
        "record_version text not null",
        "created_at timestamptz not null",
    ):
        assert column in block
    assert ResultRecord.__dataclass_fields__["model_name"].type == "str"
    assert "result_records_canonical_key_unique unique (canonical_key)" in sql


def test_parent_constraints_exist():
    sql = _sql().lower()

    for fragment in (
        "jsonb_typeof(data) = 'object'",
        "result_records_prompt_id_not_blank",
        "result_records_prompt_version_not_blank",
        "result_records_contract_name_not_blank",
        "result_records_model_name_not_blank",
        "result_records_canonical_key_not_blank",
        "result_records_content_hash_sha256",
        "content_hash ~ '^[0-9a-f]{64}$'",
        "result_records_record_version_not_blank",
    ):
        assert fragment in sql


def test_child_tables_exist_with_only_query_columns():
    sql = _sql()

    document_analysis = _table_block(sql, "document_analysis")
    findings = _table_block(sql, "findings")
    evidence = _table_block(sql, "evidence")

    assert "id uuid primary key references result_records(id) on delete restrict" in document_analysis
    assert "document_type text not null" in document_analysis
    assert "title text not null" in document_analysis
    assert "summary text not null" in document_analysis
    assert "preliminary_topics text[]" in document_analysis

    assert "id uuid primary key references result_records(id) on delete restrict" in findings
    assert "finding_type text not null" in findings
    assert "description text not null" in findings

    assert "id uuid primary key references result_records(id) on delete restrict" in evidence
    assert "quote text not null" in evidence
    assert "evidence_type text not null" in evidence
    assert "matched_chunk_id uuid references document_chunks(id) on delete restrict" in evidence


def test_common_metadata_not_duplicated_in_child_tables():
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

    for table_name in ("document_analysis", "findings", "evidence"):
        block = _table_block(sql, table_name)
        for fragment in forbidden:
            assert fragment not in block


def test_general_evidence_relation_exists():
    block = _table_block(_sql(), "result_record_evidence")

    assert "record_id uuid not null references result_records(id) on delete restrict" in block
    assert "evidence_id uuid not null references evidence(id) on delete restrict" in block
    assert "primary key (record_id, evidence_id)" in block


def test_record_type_validation_triggers_exist():
    sql = _sql().lower()

    for fragment in (
        "create or replace function validate_result_record_type",
        "validate_document_analysis_record_type",
        "perform validate_result_record_type('document_analysis', new.id)",
        "perform validate_result_record_type('finding', new.id)",
        "perform validate_result_record_type('evidence', new.id)",
        "perform validate_result_record_type('evidence', new.evidence_id)",
        "document_analysis_validate_record_type",
        "findings_validate_record_type",
        "evidence_validate_record_type",
        "result_record_evidence_validate_evidence_type",
    ):
        assert fragment in sql


def test_indexes_exist():
    sql = _sql().lower()

    for fragment in (
        "result_records_document_type_idx",
        "on result_records (document_id, record_type)",
        "result_records_content_hash_idx",
        "result_records_finding_confidence_idx",
        "where record_type = 'finding'",
        "result_records_evidence_document_idx",
        "where record_type = 'evidence'",
        "findings_type_confidence_idx",
        "evidence_matched_chunk_idx",
        "evidence_page_location_idx",
        "evidence_sheet_row_location_idx",
        "result_record_evidence_evidence_idx",
    ):
        assert fragment in sql


def test_foreign_keys_are_conservative():
    sql = _sql().lower()

    assert "references documents(id) on delete restrict" in sql
    assert "references result_records(id) on delete restrict" in sql
    assert "references document_chunks(id) on delete restrict" in sql
    assert "on delete cascade" not in sql


def test_rls_enabled_without_policies_or_grants():
    sql = _sql().lower()

    for table_name in (
        "result_records",
        "document_analysis",
        "findings",
        "evidence",
        "result_record_evidence",
    ):
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


def test_no_future_domain_tables_yet():
    sql = _sql().lower()

    forbidden_tables = (
        "pmge_projects",
        "pmge_objectives",
        "pmge_activities",
        "regulatory_agenda_initiatives",
        "regulatory_deliverables",
        "policies",
        "policy_activities",
        "policy_commitments",
        "corpus_snapshots",
        "analysis_runs",
        "analysis_stage_runs",
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
