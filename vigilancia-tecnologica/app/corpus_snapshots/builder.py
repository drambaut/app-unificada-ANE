"""Construccion de instantaneas estables del corpus."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from app.corpus_snapshots.errors import (
    InvalidCorpusSnapshotError,
    InvalidSnapshotReferenceError,
)
from app.corpus_snapshots.models import CorpusSnapshot, SnapshotRecordRef
from app.corpus_snapshots.repository import CorpusSnapshotRepository
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle, ResultRecord


class CorpusSnapshotBuilder:
    """Crea y guarda snapshots desde resultados ya persistidos."""

    def __init__(
        self,
        repository: CorpusSnapshotRepository,
        *,
        uuid_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._uuid_factory = uuid_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))

    def build_snapshot(
        self,
        *,
        documents: Sequence[Document],
        bundles: Sequence[PersistenceBundle],
        selection_criteria: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CorpusSnapshot:
        criteria = dict(selection_criteria or {})
        bundle_by_document = {bundle.document_id: bundle for bundle in bundles}
        processed_documents = sorted(
            [doc for doc in documents if doc.status == DocumentStatus.PROCESSED],
            key=lambda doc: doc.id,
        )
        if not processed_documents:
            raise InvalidCorpusSnapshotError("No hay documentos processed para el snapshot.")

        missing = [
            document.id
            for document in processed_documents
            if document.id not in bundle_by_document
        ]
        if missing:
            raise InvalidCorpusSnapshotError(
                f"Documentos processed sin PersistenceBundle: {', '.join(missing)}."
            )

        surveillance_ids = tuple(
            doc.id
            for doc in processed_documents
            if doc.source_type == SourceType.SURVEILLANCE
        )
        institutional_ids = tuple(
            doc.id
            for doc in processed_documents
            if doc.source_type == SourceType.INSTITUTIONAL_PLAN
        )
        policy_ids = tuple(
            doc.id
            for doc in processed_documents
            if doc.source_type == SourceType.POLICY_MATRIX
        )

        record_refs: list[SnapshotRecordRef] = []
        surveillance_finding_count = 0
        for document in processed_documents:
            bundle = bundle_by_document[document.id]
            if document.source_type == SourceType.SURVEILLANCE:
                surveillance_finding_count += len(bundle.findings)
            record_refs.extend(self._record_refs(bundle))

        if surveillance_ids and surveillance_finding_count == 0:
            raise InvalidCorpusSnapshotError(
                "El corpus de vigilancia debe incluir al menos un finding."
            )
        if not record_refs:
            raise InvalidCorpusSnapshotError("El snapshot debe incluir referencias.")

        snapshot_hash = self._snapshot_hash(
            surveillance_document_ids=surveillance_ids,
            institutional_plan_document_ids=institutional_ids,
            policy_matrix_document_ids=policy_ids,
            record_refs=record_refs,
            selection_criteria=criteria,
        )
        snapshot = CorpusSnapshot(
            id=self._uuid_factory(),
            created_at=self._clock(),
            snapshot_hash=snapshot_hash,
            selection_criteria=criteria,
            surveillance_document_ids=surveillance_ids,
            institutional_plan_document_ids=institutional_ids,
            policy_matrix_document_ids=policy_ids,
            record_refs=tuple(record_refs),
            metadata=dict(metadata or {}),
        )
        return self._repository.save_snapshot(snapshot)

    def _record_refs(self, bundle: PersistenceBundle) -> list[SnapshotRecordRef]:
        refs: list[SnapshotRecordRef] = []
        for record_type, records in self._records_by_type(bundle):
            for record in records:
                self._validate_record(record)
                refs.append(
                    SnapshotRecordRef(
                        record_id=record.id,
                        document_id=record.document_id,
                        record_type=record_type,
                        canonical_key=record.canonical_key,
                        content_hash=self._record_content_hash(record),
                        record_version=self._record_version(record),
                        created_at=record.created_at,
                    )
                )
        return refs

    def _records_by_type(
        self, bundle: PersistenceBundle
    ) -> list[tuple[str, list[ResultRecord]]]:
        records: list[tuple[str, list[ResultRecord]]] = []
        if bundle.document_analysis is not None:
            records.append(("document_analysis", [bundle.document_analysis]))
        records.extend(
            [
                ("finding", bundle.findings),
                ("evidence", bundle.evidence),
                ("pmge_project", bundle.pmge_projects),
                ("pmge_objective", bundle.pmge_objectives),
                ("pmge_activity", bundle.pmge_activities),
                ("agenda_initiative", bundle.regulatory_agenda_initiatives),
                ("agenda_deliverable", bundle.regulatory_deliverables),
                ("policy", bundle.policies),
                ("policy_activity", bundle.policy_activities),
                ("policy_commitment", bundle.policy_commitments),
            ]
        )
        return records

    def _validate_record(self, record: ResultRecord) -> None:
        for field_name in ("id", "document_id", "canonical_key"):
            if not getattr(record, field_name):
                raise InvalidSnapshotReferenceError(
                    f"{field_name} no puede estar vacio."
                )

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

    def _snapshot_hash(
        self,
        *,
        surveillance_document_ids: tuple[str, ...],
        institutional_plan_document_ids: tuple[str, ...],
        policy_matrix_document_ids: tuple[str, ...],
        record_refs: list[SnapshotRecordRef],
        selection_criteria: dict[str, str],
    ) -> str:
        payload = {
            "surveillance_document_ids": sorted(surveillance_document_ids),
            "institutional_plan_document_ids": sorted(institutional_plan_document_ids),
            "policy_matrix_document_ids": sorted(policy_matrix_document_ids),
            "record_refs": [
                {
                    "record_id": ref.record_id,
                    "document_id": ref.document_id,
                    "record_type": ref.record_type,
                    "canonical_key": ref.canonical_key,
                    "content_hash": ref.content_hash,
                    "record_version": ref.record_version,
                }
                for ref in sorted(record_refs, key=lambda item: item.sort_key())
            ],
            "selection_criteria": selection_criteria,
        }
        return self._sha256(payload)

    def _sha256(self, payload: dict) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

