"""Contratos inmutables consumidos por el dashboard publicado."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


class FrozenDict(Mapping):
    """Mapping profundamente inmutable con orden deterministico."""

    def __init__(self, values: Mapping | None = None) -> None:
        source = values or {}
        self._data = {
            key: _freeze(value)
            for key, value in sorted(source.items(), key=lambda item: str(item[0]))
        }

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return repr(self._data)

    def __eq__(self, other) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return False


def _freeze(value):
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _sorted_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in values))


def _sorted_views(values: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    return tuple(sorted(values, key=lambda item: getattr(item, "id", "")))


def _setattr(name: str, instance, value) -> None:
    object.__setattr__(instance, name, value)


@dataclass(frozen=True)
class PublishedRunSummary:
    run_id: str
    snapshot_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    published_at: datetime | None
    prompt_versions: Mapping[str, str]
    document_count: int
    finding_count: int
    evidence_count: int

    def __post_init__(self) -> None:
        _setattr("prompt_versions", self, FrozenDict(self.prompt_versions))


@dataclass(frozen=True)
class StrategicOverview:
    theme_count: int
    trend_count: int
    emerging_signal_count: int
    regulatory_analysis_count: int
    gap_count: int
    importance_count: int
    opportunity_count: int
    pmge_alignment_count: int
    average_importance_score: float | None = None
    average_opportunity_score: float | None = None
    average_alignment_score: float | None = None


@dataclass(frozen=True)
class ThemeView:
    id: str
    name: str
    definition: str
    scope: str
    subthemes: tuple[str, ...]
    technologies: tuple[str, ...]
    frequency_bands: tuple[str, ...]
    countries_regions: tuple[str, ...]
    organizations: tuple[str, ...]
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    change_action: str
    confidence: str
    extraction_basis: str

    def __post_init__(self) -> None:
        for field_name in _OPEN_LIST_FIELDS + ("finding_ids", "evidence_ids"):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class TrendView:
    id: str
    name: str
    description: str
    related_theme_ids: tuple[str, ...]
    direction: str
    time_horizon: str
    countries_regions: tuple[str, ...]
    organizations: tuple[str, ...]
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: str
    first_observed_date: str | None = None
    latest_observed_date: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "related_theme_ids",
            "countries_regions",
            "organizations",
            "finding_ids",
            "evidence_ids",
        ):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class EmergingSignalView:
    id: str
    title: str
    description: str
    novelty_explanation: str
    related_theme_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: str

    def __post_init__(self) -> None:
        for field_name in ("related_theme_ids", "finding_ids", "evidence_ids"):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class RegulatoryIntelligenceView:
    id: str
    theme_id: str | None
    international_situation: str
    regulatory_debate: str
    countries_regions: tuple[str, ...]
    organizations: tuple[str, ...]
    agenda_item_ids: tuple[str, ...]
    relationship_type: str
    coverage_explanation: str
    implications_for_ane: str
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: str
    extraction_basis: str

    def __post_init__(self) -> None:
        for field_name in (
            "countries_regions",
            "organizations",
            "agenda_item_ids",
            "finding_ids",
            "evidence_ids",
        ):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class GapView:
    id: str
    relationship_type: str
    description: str
    theme_id: str | None
    agenda_item_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("agenda_item_ids", "finding_ids", "evidence_ids"):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class ImportanceView:
    id: str
    subject_type: str
    subject_id: str
    dimensions: Mapping[str, float]
    importance_score: float
    level: str
    rationale: str
    evidence_ids: tuple[str, ...]
    confidence: str

    def __post_init__(self) -> None:
        _setattr("dimensions", self, FrozenDict(self.dimensions))
        _setattr("evidence_ids", self, _sorted_strings(self.evidence_ids))


@dataclass(frozen=True)
class OpportunityView:
    id: str
    theme_id: str
    policy_activity_ids: tuple[str, ...]
    dimensions: Mapping[str, float]
    opportunity_score: float
    level: str
    rationale: str
    suggested_action: str
    evidence_ids: tuple[str, ...]
    confidence: str

    def __post_init__(self) -> None:
        _setattr("dimensions", self, FrozenDict(self.dimensions))
        for field_name in ("policy_activity_ids", "evidence_ids"):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class PmgeAlignmentView:
    id: str
    theme_id: str
    pmge_project_ids: tuple[str, ...]
    dimensions: Mapping[str, float]
    alignment_score: float
    level: str
    rationale: str
    alignment_type: str
    evidence_ids: tuple[str, ...]
    confidence: str

    def __post_init__(self) -> None:
        _setattr("dimensions", self, FrozenDict(self.dimensions))
        for field_name in ("pmge_project_ids", "evidence_ids"):
            _setattr(field_name, self, _sorted_strings(getattr(self, field_name)))


@dataclass(frozen=True)
class EvidenceView:
    id: str
    document_id: str
    quote: str
    page_number: int | None
    section_title: str | None
    sheet_name: str | None
    row_reference: str | None
    matched_chunk_id: str | None


@dataclass(frozen=True)
class ProcessedDocumentView:
    id: str
    file_name: str
    file_type: str
    source_type: str
    document_date: date | None
    status: str


@dataclass(frozen=True)
class DashboardReadModel:
    """Modelo final para Streamlit, sin payloads LLM crudos.

    El servicio futuro debe leer la publicacion vigente con
    AnalysisRunRepository.get_latest_published_run(), obtener el CorpusSnapshot
    asociado, usar solo documentos y record_refs congelados en ese snapshot,
    exigir las tres etapas completed con payload y excluir records actuales
    ajenos al snapshot.

    Los IDs publicos de vistas transversales deben generarse
    deterministicamente a partir de run_id, stage, tipo de entidad e
    identificador interno de la respuesta. No se expone temporary_id.
    """

    summary: PublishedRunSummary
    strategic_overview: StrategicOverview
    themes: tuple[ThemeView, ...]
    trends: tuple[TrendView, ...]
    emerging_signals: tuple[EmergingSignalView, ...]
    regulatory_intelligence: tuple[RegulatoryIntelligenceView, ...]
    gaps: tuple[GapView, ...]
    importance: tuple[ImportanceView, ...]
    opportunities: tuple[OpportunityView, ...]
    pmge_alignment: tuple[PmgeAlignmentView, ...]
    evidence: tuple[EvidenceView, ...]
    documents: tuple[ProcessedDocumentView, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "themes",
            "trends",
            "emerging_signals",
            "regulatory_intelligence",
            "gaps",
            "importance",
            "opportunities",
            "pmge_alignment",
            "evidence",
            "documents",
        ):
            _setattr(field_name, self, _sorted_views(getattr(self, field_name)))


_OPEN_LIST_FIELDS = (
    "subthemes",
    "technologies",
    "frequency_bands",
    "countries_regions",
    "organizations",
)

