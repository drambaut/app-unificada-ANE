"""Normalizacion de respuestas estructuradas a registros persistibles."""

from __future__ import annotations

import copy
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.documents.models import Document
from app.evidence.models import EvidenceValidationReport, EvidenceValidationStatus
from app.llm.service import ExtractionResult
from app.results.errors import ResultNormalizationError
from app.results.models import PersistenceBundle, ResultRecord


class ResultNormalizer:
    """Convierte payload validado a bundle con UUIDs definitivos."""

    def __init__(
        self,
        *,
        uuid_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uuid_factory = uuid_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))

    def normalize(
        self,
        document: Document,
        extraction_result: ExtractionResult,
        evidence_report: EvidenceValidationReport,
    ) -> PersistenceBundle:
        if not evidence_report.is_valid:
            raise ResultNormalizationError("El reporte de evidencia no es valido.")
        payload = copy.deepcopy(extraction_result.payload)
        temporary_ids = self._collect_temporary_ids(payload)
        duplicates = [item for item, count in Counter(temporary_ids).items() if count > 1]
        if duplicates:
            raise ResultNormalizationError(
                f"temporary_id duplicado: {duplicates[0]}."
            )

        id_map = {temporary_id: self._uuid_factory() for temporary_id in temporary_ids}
        evidence_matches = self._verified_evidence_matches(evidence_report)

        evidence_records = []
        for evidence in payload.get("evidence", []):
            evidence_id = evidence["temporary_id"]
            matched_chunk_id = evidence_matches.get(evidence_id)
            if matched_chunk_id is None:
                raise ResultNormalizationError(
                    f"evidencia sin validacion verificada: {evidence_id}."
                )
            evidence_records.append(
                self._record(
                    document=document,
                    source=evidence,
                    extraction_result=extraction_result,
                    id_map=id_map,
                    canonical_key=self._evidence_key(
                        document.id, evidence, evidence_matches
                    ),
                    extra_data={
                        "matched_chunk_id": matched_chunk_id,
                    },
                )
            )

        return self._deduplicate_canonical_keys(
            PersistenceBundle(
                document_id=document.id,
                document_analysis=self._one(
                    document,
                    payload.get("document_analysis"),
                    extraction_result,
                    id_map,
                    self._analysis_key,
                ),
                findings=self._many(
                    document,
                    payload.get("findings", []),
                    extraction_result,
                    id_map,
                    self._finding_key,
                ),
                evidence=evidence_records,
                pmge_projects=self._many(
                    document,
                    payload.get("pmge_projects", []),
                    extraction_result,
                    id_map,
                    self._pmge_project_key,
                ),
                pmge_objectives=self._many(
                    document,
                    payload.get("objectives", []),
                    extraction_result,
                    id_map,
                    self._generic_key("pmge_objective", "objective_text"),
                ),
                pmge_activities=self._many(
                    document,
                    payload.get("activities", []),
                    extraction_result,
                    id_map,
                    self._generic_key("pmge_activity", "activity_name"),
                )
                if extraction_result.contract_name == "InstitutionalPlanExtraction"
                else [],
                regulatory_agenda_initiatives=self._many(
                    document,
                    payload.get("regulatory_agenda_initiatives", []),
                    extraction_result,
                    id_map,
                    self._agenda_initiative_key,
                ),
                regulatory_deliverables=self._many(
                    document,
                    payload.get("regulatory_agenda_deliverables", []),
                    extraction_result,
                    id_map,
                    self._agenda_deliverable_key,
                ),
                policies=self._many(
                    document,
                    payload.get("policies", []),
                    extraction_result,
                    id_map,
                    self._generic_key("policy", "policy_name"),
                ),
                policy_activities=self._many(
                    document,
                    payload.get("activities", []),
                    extraction_result,
                    id_map,
                    self._policy_activity_key,
                )
                if extraction_result.contract_name == "PolicyMatrixExtraction"
                else [],
                policy_commitments=self._many(
                    document,
                    payload.get("commitments", []),
                    extraction_result,
                    id_map,
                    self._policy_commitment_key,
                ),
            )
        )

    def _one(
        self,
        document: Document,
        source: dict | None,
        extraction_result: ExtractionResult,
        id_map: dict[str, str],
        key_builder,
    ) -> ResultRecord | None:
        if source is None:
            return None
        return self._record(
            document=document,
            source=source,
            extraction_result=extraction_result,
            id_map=id_map,
            canonical_key=key_builder(document.id, source, id_map),
        )

    def _many(
        self,
        document: Document,
        sources: list[dict],
        extraction_result: ExtractionResult,
        id_map: dict[str, str],
        key_builder,
    ) -> list[ResultRecord]:
        return [
            self._record(
                document=document,
                source=source,
                extraction_result=extraction_result,
                id_map=id_map,
                canonical_key=key_builder(document.id, source, id_map),
            )
            for source in sources
        ]

    def _record(
        self,
        *,
        document: Document,
        source: dict,
        extraction_result: ExtractionResult,
        id_map: dict[str, str],
        canonical_key: str,
        extra_data: dict[str, Any] | None = None,
    ) -> ResultRecord:
        temporary_id = source.get("temporary_id")
        if temporary_id not in id_map:
            raise ResultNormalizationError(f"temporary_id inexistente: {temporary_id}.")
        data = self._replace_references(copy.deepcopy(source), id_map)
        data.pop("temporary_id", None)
        if extra_data:
            data.update(extra_data)
        return ResultRecord(
            id=id_map[temporary_id],
            document_id=document.id,
            data=data,
            prompt_id=extraction_result.prompt_id,
            prompt_version=extraction_result.prompt_version,
            contract_name=extraction_result.contract_name,
            model_name=extraction_result.model_name,
            created_at=self._clock(),
            canonical_key=canonical_key,
            confidence=source.get("confidence"),
            extraction_basis=source.get("extraction_basis"),
        )

    def _replace_references(self, value, id_map: dict[str, str]):
        if isinstance(value, dict):
            replaced = {}
            for key, child in value.items():
                if key == "evidence_ids":
                    replaced[key] = [self._map_id(item, id_map) for item in child]
                elif key.endswith("_temporary_id"):
                    replaced[key.replace("_temporary_id", "_id")] = self._map_id(
                        child, id_map
                    )
                else:
                    replaced[key] = self._replace_references(child, id_map)
            return replaced
        if isinstance(value, list):
            return [self._replace_references(item, id_map) for item in value]
        return value

    def _map_id(self, temporary_id: str, id_map: dict[str, str]) -> str:
        if temporary_id not in id_map:
            raise ResultNormalizationError(
                f"referencia temporal inexistente: {temporary_id}."
            )
        return id_map[temporary_id]

    def _collect_temporary_ids(self, value) -> list[str]:
        found: list[str] = []
        self._walk_temporary_ids(value, found)
        return found

    def _walk_temporary_ids(self, value, found: list[str]) -> None:
        if isinstance(value, dict):
            if "temporary_id" in value:
                found.append(value["temporary_id"])
            for child in value.values():
                self._walk_temporary_ids(child, found)
        elif isinstance(value, list):
            for item in value:
                self._walk_temporary_ids(item, found)

    def _verified_evidence_matches(
        self, evidence_report: EvidenceValidationReport
    ) -> dict[str, str]:
        matches = {}
        for item in evidence_report.items:
            if item.status != EvidenceValidationStatus.VERIFIED:
                raise ResultNormalizationError(
                    f"evidencia no verificada: {item.evidence_id}."
                )
            if not item.matched_chunk_id:
                raise ResultNormalizationError(
                    f"evidencia sin matched_chunk_id: {item.evidence_id}."
                )
            matches[item.evidence_id] = item.matched_chunk_id
        return matches

    def _normalize_key_part(self, value: Any) -> str:
        normalized = unicodedata.normalize("NFKC", "" if value is None else str(value))
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip().casefold()

    def _join_key(self, *parts: Any) -> str:
        return "|".join(self._normalize_key_part(part) for part in parts)

    def _analysis_key(self, document_id: str, source: dict, _id_map: dict) -> str:
        return self._join_key("document_analysis", document_id)

    def _finding_key(self, document_id: str, source: dict, _id_map: dict) -> str:
        return self._join_key(
            "finding", document_id, source.get("title"), source.get("finding_type")
        )

    def _pmge_project_key(self, document_id: str, source: dict, _id_map: dict) -> str:
        return self._join_key("pmge_project", document_id, source.get("project_name"))

    def _agenda_initiative_key(
        self, document_id: str, source: dict, _id_map: dict
    ) -> str:
        return self._join_key(
            "agenda_initiative",
            document_id,
            source.get("initiative_name"),
            source.get("period"),
        )

    def _policy_activity_key(
        self, document_id: str, source: dict, id_map: dict
    ) -> str:
        policy_id = source.get("policy_temporary_id")
        mapped_policy_id = id_map.get(policy_id, policy_id)
        return self._join_key(
            "policy_activity",
            document_id,
            mapped_policy_id,
            source.get("activity_name"),
        )

    def _agenda_deliverable_key(
        self, document_id: str, source: dict, id_map: dict
    ) -> str:
        initiative_id = source.get("initiative_temporary_id")
        mapped_initiative_id = id_map.get(initiative_id, initiative_id)
        return self._join_key(
            "agenda_deliverable",
            document_id,
            mapped_initiative_id,
            source.get("deliverable_name"),
        )

    def _policy_commitment_key(
        self, document_id: str, source: dict, id_map: dict
    ) -> str:
        activity_id = source.get("policy_activity_temporary_id")
        mapped_activity_id = id_map.get(activity_id, activity_id)
        return self._join_key(
            "policy_commitment",
            document_id,
            mapped_activity_id,
            source.get("commitment_text"),
        )

    def _evidence_key(
        self, document_id: str, source: dict, evidence_matches: dict[str, str]
    ) -> str:
        return self._join_key(
            "evidence",
            document_id,
            evidence_matches.get(source.get("temporary_id")),
            source.get("quote"),
        )

    def _generic_key(self, prefix: str, field: str):
        def build(document_id: str, source: dict, _id_map: dict) -> str:
            return self._join_key(prefix, document_id, source.get(field))

        return build

    def _deduplicate_canonical_keys(self, bundle: PersistenceBundle) -> PersistenceBundle:
        seen: dict[str, int] = {}

        def dedupe_record(record: ResultRecord | None) -> ResultRecord | None:
            if record is None:
                return None
            count = seen.get(record.canonical_key, 0) + 1
            seen[record.canonical_key] = count
            if count == 1:
                return record
            return replace(record, canonical_key=f"{record.canonical_key}|duplicate-{count}")

        def dedupe_many(records: list[ResultRecord]) -> list[ResultRecord]:
            return [record for record in (dedupe_record(item) for item in records) if record]

        return PersistenceBundle(
            document_id=bundle.document_id,
            document_analysis=dedupe_record(bundle.document_analysis),
            findings=dedupe_many(bundle.findings),
            evidence=dedupe_many(bundle.evidence),
            pmge_projects=dedupe_many(bundle.pmge_projects),
            pmge_objectives=dedupe_many(bundle.pmge_objectives),
            pmge_activities=dedupe_many(bundle.pmge_activities),
            regulatory_agenda_initiatives=dedupe_many(bundle.regulatory_agenda_initiatives),
            regulatory_deliverables=dedupe_many(bundle.regulatory_deliverables),
            policies=dedupe_many(bundle.policies),
            policy_activities=dedupe_many(bundle.policy_activities),
            policy_commitments=dedupe_many(bundle.policy_commitments),
        )
