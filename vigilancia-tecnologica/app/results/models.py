"""Modelos inmutables para resultados persistibles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ResultRecord:
    id: str
    document_id: str
    data: dict[str, Any]
    prompt_id: str
    prompt_version: str
    contract_name: str
    model_name: str
    created_at: datetime
    canonical_key: str
    confidence: str | None = None
    extraction_basis: str | None = None


@dataclass(frozen=True)
class PersistenceBundle:
    document_id: str
    document_analysis: ResultRecord | None = None
    findings: list[ResultRecord] = field(default_factory=list)
    evidence: list[ResultRecord] = field(default_factory=list)
    pmge_projects: list[ResultRecord] = field(default_factory=list)
    pmge_objectives: list[ResultRecord] = field(default_factory=list)
    pmge_activities: list[ResultRecord] = field(default_factory=list)
    regulatory_agenda_initiatives: list[ResultRecord] = field(default_factory=list)
    regulatory_deliverables: list[ResultRecord] = field(default_factory=list)
    policies: list[ResultRecord] = field(default_factory=list)
    policy_activities: list[ResultRecord] = field(default_factory=list)
    policy_commitments: list[ResultRecord] = field(default_factory=list)

    def all_records(self) -> list[ResultRecord]:
        records: list[ResultRecord] = []
        if self.document_analysis is not None:
            records.append(self.document_analysis)
        for collection in (
            self.findings,
            self.evidence,
            self.pmge_projects,
            self.pmge_objectives,
            self.pmge_activities,
            self.regulatory_agenda_initiatives,
            self.regulatory_deliverables,
            self.policies,
            self.policy_activities,
            self.policy_commitments,
        ):
            records.extend(collection)
        return records
