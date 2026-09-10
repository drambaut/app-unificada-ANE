"""Construccion de contextos para prompts transversales."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC
from typing import Any

from app.corpus_snapshots.errors import InvalidCorpusSnapshotError
from app.corpus_snapshots.models import CorpusSnapshot, PromptContext, SnapshotRecordRef
from app.documents.models import Document
from app.results.models import PersistenceBundle, ResultRecord


class CorpusContextBuilder:
    """Construye payloads minimos desde un CorpusSnapshot verificado."""

    def __init__(self, *, max_records_by_type: dict[str, int] | None = None) -> None:
        self._max_records_by_type = dict(max_records_by_type or {})
        for record_type, limit in self._max_records_by_type.items():
            if limit <= 0:
                raise InvalidCorpusSnapshotError(
                    f"Limite invalido para {record_type}: debe ser mayor que cero."
                )

    def build_thematic_landscape_context(
        self,
        *,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        prompt_id: str,
        prompt_version: str,
    ) -> PromptContext:
        verified = self._verified_records(snapshot, documents, bundles)
        surveillance_ids = set(snapshot.surveillance_document_ids)
        document_analysis = self._records(
            verified, "document_analysis", document_ids=surveillance_ids
        )
        findings = self._records(verified, "finding", document_ids=surveillance_ids)
        evidence = self._evidence_for_records(
            verified, [*document_analysis, *findings], document_ids=surveillance_ids
        )

        payload = {
            "snapshot_id": snapshot.id,
            "documents": self._document_payloads(documents, surveillance_ids),
            "document_analysis": self._record_payloads(document_analysis),
            "findings": self._record_payloads(findings),
            "evidence": self._record_payloads(evidence),
        }
        return self._context(snapshot, prompt_id, prompt_version, payload)

    def build_regulatory_intelligence_context(
        self,
        *,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        thematic_result: dict | None,
        prompt_id: str,
        prompt_version: str,
    ) -> PromptContext:
        if thematic_result is None:
            raise InvalidCorpusSnapshotError("thematic_result es obligatorio.")

        verified = self._verified_records(snapshot, documents, bundles)
        surveillance_ids = set(snapshot.surveillance_document_ids)
        institutional_ids = set(snapshot.institutional_plan_document_ids)
        findings = self._records(verified, "finding", document_ids=surveillance_ids)
        agenda = self._records(
            verified, "agenda_initiative", document_ids=institutional_ids
        )
        deliverables = self._records(
            verified, "agenda_deliverable", document_ids=institutional_ids
        )
        evidence = self._evidence_for_records(
            verified,
            [*findings, *agenda, *deliverables],
            document_ids=surveillance_ids | institutional_ids,
        )

        payload = {
            "snapshot_id": snapshot.id,
            "thematic_landscape": thematic_result,
            "surveillance": {
                "findings": self._record_payloads(findings),
                "evidence": self._record_payloads(
                    [item for item in evidence if item.document_id in surveillance_ids]
                ),
            },
            "agenda_regulatoria": {
                "initiatives": self._record_payloads(agenda),
                "deliverables": self._record_payloads(deliverables),
                "evidence": self._record_payloads(
                    [item for item in evidence if item.document_id in institutional_ids]
                ),
            },
        }
        return self._context(snapshot, prompt_id, prompt_version, payload)

    def build_strategic_assessment_context(
        self,
        *,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        thematic_result: dict | None,
        prompt_id: str,
        prompt_version: str,
    ) -> PromptContext:
        if thematic_result is None:
            raise InvalidCorpusSnapshotError("thematic_result es obligatorio.")

        verified = self._verified_records(snapshot, documents, bundles)
        surveillance_ids = set(snapshot.surveillance_document_ids)
        institutional_ids = set(snapshot.institutional_plan_document_ids)
        policy_ids = set(snapshot.policy_matrix_document_ids)

        findings = self._records(verified, "finding", document_ids=surveillance_ids)
        pmge_records = [
            *self._records(verified, "pmge_project", document_ids=institutional_ids),
            *self._records(verified, "pmge_objective", document_ids=institutional_ids),
            *self._records(verified, "pmge_activity", document_ids=institutional_ids),
        ]
        policy_records = [
            *self._records(verified, "policy", document_ids=policy_ids),
            *self._records(verified, "policy_activity", document_ids=policy_ids),
            *self._records(verified, "policy_commitment", document_ids=policy_ids),
        ]
        evidence = self._evidence_for_records(
            verified,
            [*findings, *pmge_records, *policy_records],
            document_ids=surveillance_ids | institutional_ids | policy_ids,
        )

        payload = {
            "snapshot_id": snapshot.id,
            "thematic_landscape": thematic_result,
            "importance_inputs": {
                "findings": self._record_payloads(findings),
                "evidence": self._record_payloads(
                    [item for item in evidence if item.document_id in surveillance_ids]
                ),
            },
            "opportunity_inputs": {
                "policies": self._record_payloads(
                    self._records(verified, "policy", document_ids=policy_ids)
                ),
                "policy_activities": self._record_payloads(
                    self._records(verified, "policy_activity", document_ids=policy_ids)
                ),
                "policy_commitments": self._record_payloads(
                    self._records(verified, "policy_commitment", document_ids=policy_ids)
                ),
                "evidence": self._record_payloads(
                    [item for item in evidence if item.document_id in policy_ids]
                ),
            },
            "alignment_inputs": {
                "pmge_projects": self._record_payloads(
                    self._records(verified, "pmge_project", document_ids=institutional_ids)
                ),
                "pmge_objectives": self._record_payloads(
                    self._records(verified, "pmge_objective", document_ids=institutional_ids)
                ),
                "pmge_activities": self._record_payloads(
                    self._records(verified, "pmge_activity", document_ids=institutional_ids)
                ),
                "evidence": self._record_payloads(
                    [item for item in evidence if item.document_id in institutional_ids]
                ),
            },
        }
        return self._context(snapshot, prompt_id, prompt_version, payload)

    def _verified_records(
        self,
        snapshot: CorpusSnapshot,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
    ) -> dict[str, ResultRecord]:
        document_ids = set(
            snapshot.surveillance_document_ids
            + snapshot.institutional_plan_document_ids
            + snapshot.policy_matrix_document_ids
        )
        provided_document_ids = {document.id for document in documents}
        missing_documents = sorted(document_ids - provided_document_ids)
        if missing_documents:
            raise InvalidCorpusSnapshotError(
                f"Documentos faltantes para snapshot: {', '.join(missing_documents)}."
            )

        refs_by_id = {ref.record_id: ref for ref in snapshot.record_refs}
        records_by_id: dict[str, ResultRecord] = {}
        for bundle in bundles:
            if bundle.document_id not in document_ids:
                continue
            for record in bundle.all_records():
                if record.id not in refs_by_id:
                    raise InvalidCorpusSnapshotError(
                        f"Record ajeno al snapshot: {record.id}."
                    )
                records_by_id[record.id] = record

        missing_records = sorted(set(refs_by_id) - set(records_by_id))
        if missing_records:
            raise InvalidCorpusSnapshotError(
                f"Records faltantes para snapshot: {', '.join(missing_records)}."
            )

        for ref in snapshot.record_refs:
            record = records_by_id[ref.record_id]
            self._verify_ref(ref, record)
        return records_by_id

    def _verify_ref(self, ref: SnapshotRecordRef, record: ResultRecord) -> None:
        if ref.document_id != record.document_id:
            raise InvalidCorpusSnapshotError(
                f"Documento diferente para record {record.id}."
            )
        if ref.canonical_key != record.canonical_key:
            raise InvalidCorpusSnapshotError(
                f"canonical_key diferente para record {record.id}."
            )
        if ref.content_hash != self._record_content_hash(record):
            raise InvalidCorpusSnapshotError(
                f"content_hash diferente para record {record.id}."
            )
        if ref.record_version != self._record_version(record):
            raise InvalidCorpusSnapshotError(
                f"record_version diferente para record {record.id}."
            )

    def _records(
        self,
        records_by_id: dict[str, ResultRecord],
        record_type: str,
        *,
        document_ids: set[str],
    ) -> list[ResultRecord]:
        records = [
            record
            for record in records_by_id.values()
            if record.document_id in document_ids
            and record.canonical_key.startswith(f"{record_type}|")
        ]
        return sorted(records, key=lambda record: record.id)

    def _evidence_for_records(
        self,
        records_by_id: dict[str, ResultRecord],
        records: Sequence[ResultRecord],
        *,
        document_ids: set[str],
    ) -> list[ResultRecord]:
        evidence_ids: set[str] = set()
        for record in records:
            evidence_ids.update(record.data.get("evidence_ids", []))

        evidence = [
            records_by_id[evidence_id]
            for evidence_id in sorted(evidence_ids)
            if evidence_id in records_by_id
            and records_by_id[evidence_id].document_id in document_ids
            and records_by_id[evidence_id].canonical_key.startswith("evidence|")
        ]
        return evidence

    def _record_payloads(self, records: Sequence[ResultRecord]) -> list[dict]:
        payloads = [
            {
                "id": record.id,
                "document_id": record.document_id,
                "data": record.data,
                "confidence": record.confidence,
                "extraction_basis": record.extraction_basis,
            }
            for record in records
        ]
        return payloads

    def _document_payloads(
        self, documents: Sequence[Document], document_ids: set[str]
    ) -> list[dict]:
        return [
            {
                "id": document.id,
                "file_name": document.file_name,
                "file_type": document.file_type,
                "document_date": document.document_date.isoformat()
                if document.document_date
                else None,
            }
            for document in sorted(documents, key=lambda item: item.id)
            if document.id in document_ids
        ]

    def _context(
        self,
        snapshot: CorpusSnapshot,
        prompt_id: str,
        prompt_version: str,
        payload: dict[str, Any],
    ) -> PromptContext:
        included_ids = tuple(sorted(self._collect_ids(payload)))
        if not included_ids:
            raise InvalidCorpusSnapshotError("El contexto no contiene registros.")

        limited_payload, omitted_counts = self._apply_limits(payload)
        context_hash = self._sha256(
            {
                "snapshot_id": snapshot.id,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "payload": limited_payload,
                "included_ids": sorted(self._collect_ids(limited_payload)),
                "omitted_counts": omitted_counts,
            }
        )
        return PromptContext(
            snapshot_id=snapshot.id,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            payload=limited_payload,
            included_ids=tuple(sorted(self._collect_ids(limited_payload))),
            omitted_counts=omitted_counts,
            context_hash=context_hash,
        )

    def _apply_limits(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        if not self._max_records_by_type:
            return payload, {}
        omitted: dict[str, int] = {}
        limited = json.loads(json.dumps(payload, default=str))
        self._limit_lists(limited, omitted)
        return limited, omitted

    def _limit_lists(self, value: Any, omitted: dict[str, int]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, list) and key in self._max_records_by_type:
                    limit = self._max_records_by_type[key]
                    if len(child) > limit:
                        omitted[key] = omitted.get(key, 0) + len(child) - limit
                        value[key] = child[:limit]
                self._limit_lists(value[key], omitted)
        elif isinstance(value, list):
            for child in value:
                self._limit_lists(child, omitted)

    def _collect_ids(self, value: Any) -> set[str]:
        ids: set[str] = set()
        if isinstance(value, dict):
            if isinstance(value.get("id"), str):
                ids.add(value["id"])
            for child in value.values():
                ids.update(self._collect_ids(child))
        elif isinstance(value, list | tuple):
            for child in value:
                ids.update(self._collect_ids(child))
        return ids

    def _record_content_hash(self, record: ResultRecord) -> str:
        payload = {
            "id": record.id,
            "document_id": record.document_id,
            "data": record.data,
            "canonical_key": record.canonical_key,
            "confidence": record.confidence,
            "extraction_basis": record.extraction_basis,
        }
        return self._sha256(payload)

    def _record_version(self, record: ResultRecord) -> str:
        return record.created_at.astimezone(UTC).isoformat()

    def _sha256(self, payload: dict) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
