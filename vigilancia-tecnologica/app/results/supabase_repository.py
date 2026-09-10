"""Repositorio de resultados normalizados sobre Supabase/PostgREST."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Callable

from app.core.settings import Settings, load_settings
from app.results.errors import DuplicateResultError, ResultPersistenceError
from app.results.models import PersistenceBundle, ResultRecord
from app.storage.errors import StorageConfigurationError


RESULT_COLLECTIONS: tuple[tuple[str, str, str], ...] = (
    ("document_analysis", "document_analysis", "document_analysis"),
    ("findings", "finding", "findings"),
    ("evidence", "evidence", "evidence"),
    ("pmge_projects", "pmge_project", "pmge_projects"),
    ("pmge_objectives", "pmge_objective", "pmge_objectives"),
    ("pmge_activities", "pmge_activity", "pmge_activities"),
    (
        "regulatory_agenda_initiatives",
        "agenda_initiative",
        "regulatory_agenda_initiatives",
    ),
    ("regulatory_deliverables", "agenda_deliverable", "regulatory_deliverables"),
    ("policies", "policy", "policies"),
    ("policy_activities", "policy_activity", "policy_activities"),
    ("policy_commitments", "policy_commitment", "policy_commitments"),
)


class SupabaseResultRepository:
    """Implementacion Supabase del contrato `ResultRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client
        self._client_factory = client_factory

    def save_bundle(self, bundle: PersistenceBundle) -> PersistenceBundle:
        if self.get_bundle(bundle.document_id) is not None:
            raise DuplicateResultError(
                f"Ya existe resultado persistido para {bundle.document_id}."
            )

        records_by_id = {
            record.id: record
            for _attribute, _record_type, _table, record in _iter_records(bundle)
        }
        canonical_keys = [record.canonical_key for record in records_by_id.values()]
        if len(canonical_keys) != len(set(canonical_keys)):
            raise DuplicateResultError("El bundle contiene canonical_key duplicada.")
        for key in canonical_keys:
            if self.has_canonical_key(key):
                raise DuplicateResultError(f"canonical_key ya existe: {key}.")

        try:
            self._client_instance().rpc(
                "persist_result_bundle",
                {"bundle": _bundle_to_rpc_payload(bundle)},
            ).execute()
        except DuplicateResultError:
            raise
        except Exception as exc:
            raise ResultPersistenceError(
                f"No fue posible persistir resultados para {bundle.document_id}."
            ) from exc
        return bundle

    def get_bundle(self, document_id: str) -> PersistenceBundle | None:
        rows = (
            self._table("result_records")
            .select("*")
            .eq("document_id", document_id)
            .order("created_at")
            .execute()
            .data
        )
        if not rows:
            return None

        records_by_type: dict[str, list[ResultRecord]] = {}
        for row in rows:
            records_by_type.setdefault(row["record_type"], []).append(
                _record_from_parent_row(row)
            )

        document_analysis = _one(records_by_type.get("document_analysis", []))
        return PersistenceBundle(
            document_id=document_id,
            document_analysis=document_analysis,
            findings=records_by_type.get("finding", []),
            evidence=records_by_type.get("evidence", []),
            pmge_projects=records_by_type.get("pmge_project", []),
            pmge_objectives=records_by_type.get("pmge_objective", []),
            pmge_activities=records_by_type.get("pmge_activity", []),
            regulatory_agenda_initiatives=records_by_type.get("agenda_initiative", []),
            regulatory_deliverables=records_by_type.get("agenda_deliverable", []),
            policies=records_by_type.get("policy", []),
            policy_activities=records_by_type.get("policy_activity", []),
            policy_commitments=records_by_type.get("policy_commitment", []),
        )

    def has_canonical_key(self, canonical_key: str) -> bool:
        rows = (
            self._table("result_records")
            .select("id")
            .eq("canonical_key", canonical_key)
            .limit(1)
            .execute()
            .data
        )
        return bool(rows)

    def _table(self, name: str):
        return self._client_instance().table(name)

    def _client_instance(self):
        if self._client is not None:
            return self._client
        key = self._settings.supabase_backend_key
        if not self._settings.supabase_url or not key:
            raise StorageConfigurationError(
                "SUPABASE_URL y SUPABASE_KEY son requeridos para Supabase."
            )
        factory = self._client_factory or self._default_client_factory
        self._client = factory(self._settings.supabase_url, key)
        return self._client

    def _default_client_factory(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError as exc:
            raise StorageConfigurationError(
                "Instale la dependencia 'supabase' para usar repositorios Supabase."
            ) from exc
        return create_client(url, key)


def _iter_records(bundle: PersistenceBundle):
    for attribute, record_type, table in RESULT_COLLECTIONS:
        value = getattr(bundle, attribute)
        records = [value] if isinstance(value, ResultRecord) else list(value or [])
        for record in records:
            yield attribute, record_type, table, record


def _bundle_to_rpc_payload(bundle: PersistenceBundle) -> dict[str, Any]:
    records_by_id = {
        record.id: record
        for _attribute, _record_type, _table, record in _iter_records(bundle)
    }
    return {
        "document_id": bundle.document_id,
        "result_records": [
            _record_to_parent_row(record, record_type=record_type)
            for _attribute, record_type, _table, record in _iter_records(bundle)
        ],
        "child_records": [
            {"table": table, "data": _record_to_child_row(table, record)}
            for _attribute, _record_type, table, record in _iter_records(bundle)
        ],
        "evidence_links": [
            {"record_id": record.id, "evidence_id": evidence_id}
            for record in records_by_id.values()
            for evidence_id in record.data.get("evidence_ids", [])
            if evidence_id in records_by_id
        ],
    }


def _record_to_parent_row(record: ResultRecord, *, record_type: str) -> dict[str, Any]:
    return {
        "id": record.id,
        "document_id": record.document_id,
        "record_type": record_type,
        "data": record.data,
        "prompt_id": record.prompt_id,
        "prompt_version": record.prompt_version,
        "contract_name": record.contract_name,
        "model_name": record.model_name,
        "canonical_key": record.canonical_key,
        "confidence": record.confidence,
        "extraction_basis": record.extraction_basis,
        "content_hash": _content_hash(record),
        "record_version": _record_version(record),
        "created_at": record.created_at.isoformat(),
    }


def _record_from_parent_row(row: dict[str, Any]) -> ResultRecord:
    return ResultRecord(
        id=row["id"],
        document_id=row["document_id"],
        data=row["data"],
        prompt_id=row["prompt_id"],
        prompt_version=row["prompt_version"],
        contract_name=row["contract_name"],
        model_name=row["model_name"],
        created_at=_parse_datetime(row["created_at"]),
        canonical_key=row["canonical_key"],
        confidence=row.get("confidence"),
        extraction_basis=row.get("extraction_basis"),
    )


def _record_to_child_row(table: str, record: ResultRecord) -> dict[str, Any]:
    data = record.data
    if table == "document_analysis":
        return {
            "id": record.id,
            "document_type": data["document_type"],
            "title": data["title"],
            "summary": data["summary"],
            "publication_date": data.get("publication_date"),
            "document_date": data.get("document_date"),
            "language": data.get("language"),
            "preliminary_topics": data.get("preliminary_topics", []),
            "technologies": data.get("technologies", []),
            "frequency_bands": data.get("frequency_bands", []),
            "countries_regions": data.get("countries_regions", []),
            "organizations": data.get("organizations", []),
            "actors": data.get("actors", []),
            "keywords": data.get("keywords", []),
        }
    if table == "findings":
        return {
            "id": record.id,
            "finding_type": data["finding_type"],
            "title": data["title"],
            "description": data["description"],
            "preliminary_topics": data.get("preliminary_topics", []),
            "technologies": data.get("technologies", []),
            "frequency_bands": data.get("frequency_bands", []),
            "countries_regions": data.get("countries_regions", []),
            "organizations": data.get("organizations", []),
        }
    if table == "evidence":
        return {
            "id": record.id,
            "quote": data["quote"],
            "evidence_type": data["evidence_type"],
            "page_number": data.get("page_number"),
            "sheet_name": data.get("sheet_name"),
            "row_reference": data.get("row_reference"),
            "section_title": data.get("section_title"),
            "matched_chunk_id": data.get("matched_chunk_id"),
        }
    if table == "pmge_projects":
        return {
            "id": record.id,
            "project_name": data["project_name"],
            "description": data["description"],
            "objectives": data.get("objectives", []),
            "activities": data.get("activities", []),
            "expected_outputs": data.get("expected_outputs", []),
            "period": data.get("period"),
            "responsible_area": data.get("responsible_area"),
        }
    if table == "pmge_objectives":
        return {
            "id": record.id,
            "project_id": data.get("project_id"),
            "objective_text": data["objective_text"],
        }
    if table == "pmge_activities":
        return {
            "id": record.id,
            "project_id": data.get("project_id"),
            "objective_id": data.get("objective_id"),
            "activity_name": data["activity_name"],
            "activity_description": data["activity_description"],
            "responsible_area": data.get("responsible_area"),
            "period": data.get("period"),
        }
    if table == "regulatory_agenda_initiatives":
        return {
            "id": record.id,
            "initiative_name": data["initiative_name"],
            "regulatory_objective": data["regulatory_objective"],
            "deliverables": data.get("deliverables", []),
            "period": data.get("period"),
            "responsible_area": data.get("responsible_area"),
        }
    if table == "regulatory_deliverables":
        return {
            "id": record.id,
            "initiative_id": data["initiative_id"],
            "deliverable_name": data["deliverable_name"],
            "description": data.get("description"),
            "period": data.get("period"),
        }
    if table == "policies":
        return {
            "id": record.id,
            "policy_name": data["policy_name"],
            "instrument_name": data.get("instrument_name"),
            "policy_axis": data.get("policy_axis"),
            "description": data.get("description"),
        }
    if table == "policy_activities":
        return {
            "id": record.id,
            "policy_id": data.get("policy_id"),
            "activity_name": data["activity_name"],
            "activity_description": data["activity_description"],
            "responsible_area": data.get("responsible_area"),
            "execution_period": data.get("execution_period"),
            "commitments": data.get("commitments", []),
            "keywords": data.get("keywords", []),
        }
    if table == "policy_commitments":
        return {
            "id": record.id,
            "policy_activity_id": data.get("policy_activity_id"),
            "commitment_text": data["commitment_text"],
            "responsible_area": data.get("responsible_area"),
            "period": data.get("period"),
        }
    raise ResultPersistenceError(f"Tipo de tabla no soportado: {table}.")


def _content_hash(record: ResultRecord) -> str:
    payload = json.dumps(
        {
            "id": record.id,
            "document_id": record.document_id,
            "data": record.data,
            "canonical_key": record.canonical_key,
            "confidence": record.confidence,
            "extraction_basis": record.extraction_basis,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_version(record: ResultRecord) -> str:
    return record.created_at.astimezone(UTC).isoformat()


def _one(records: list[ResultRecord]) -> ResultRecord | None:
    return records[0] if records else None


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
