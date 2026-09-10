"""Mapeo de resultados publicados a vistas estables de dashboard."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from app.analysis_runs.models import AnalysisRun, AnalysisStage, AnalysisStageRun
from app.dashboard_read.errors import DashboardMappingError
from app.dashboard_read.models import (
    EmergingSignalView,
    EvidenceView,
    GapView,
    ImportanceView,
    OpportunityView,
    PmgeAlignmentView,
    ProcessedDocumentView,
    PublishedRunSummary,
    RegulatoryIntelligenceView,
    StrategicOverview,
    ThemeView,
    TrendView,
)
from app.documents.models import Document
from app.results.models import ResultRecord


GAP_RELATIONSHIP_TYPES = {"gap", "partially_covered", "tension"}


def public_id(run_id: str, stage: AnalysisStage, entity_type: str, internal_id: str) -> str:
    """Genera ID publico deterministico sin exponer temporary_id."""

    digest = hashlib.sha256(
        f"{run_id}|{stage.value}|{entity_type}|{internal_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{entity_type}-{digest}"


def build_summary(
    *,
    run: AnalysisRun,
    stages: Iterable[AnalysisStageRun],
    documents: Iterable[Document],
    findings: Iterable[ResultRecord],
    evidence: Iterable[ResultRecord],
) -> PublishedRunSummary:
    return PublishedRunSummary(
        run_id=run.id,
        snapshot_id=run.corpus_snapshot_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        created_at=run.created_at,
        completed_at=run.completed_at,
        published_at=run.published_at,
        prompt_versions={
            stage.stage.value: stage.prompt_version
            for stage in sorted(stages, key=lambda item: item.stage.value)
        },
        document_count=len(list(documents)),
        finding_count=len(list(findings)),
        evidence_count=len(list(evidence)),
    )


def map_documents(documents: Iterable[Document]) -> tuple[ProcessedDocumentView, ...]:
    return tuple(
        ProcessedDocumentView(
            id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            source_type=document.source_type.value
            if hasattr(document.source_type, "value")
            else str(document.source_type),
            document_date=document.document_date,
            status=document.status.value if hasattr(document.status, "value") else str(document.status),
        )
        for document in sorted(documents, key=lambda item: item.id)
    )


def map_evidence(records: Iterable[ResultRecord]) -> tuple[EvidenceView, ...]:
    seen: set[str] = set()
    views: list[EvidenceView] = []
    for record in sorted(records, key=lambda item: item.id):
        if record.id in seen:
            continue
        seen.add(record.id)
        data = record.data
        views.append(
            EvidenceView(
                id=record.id,
                document_id=record.document_id,
                quote=str(data.get("quote", "")),
                page_number=data.get("page_number"),
                section_title=data.get("section_title"),
                sheet_name=data.get("sheet_name"),
                row_reference=data.get("row_reference"),
                matched_chunk_id=data.get("matched_chunk_id"),
            )
        )
    return tuple(views)


def map_thematic_landscape(
    *, run_id: str, payload: Mapping[str, Any]
) -> tuple[
    tuple[ThemeView, ...],
    tuple[TrendView, ...],
    tuple[EmergingSignalView, ...],
    dict[str, str],
]:
    theme_id_map: dict[str, str] = {}
    themes: list[ThemeView] = []
    for item in payload.get("themes", []):
        internal_id = _internal_id(item, "theme")
        view_id = public_id(
            run_id, AnalysisStage.THEMATIC_LANDSCAPE, "theme", internal_id
        )
        theme_id_map[internal_id] = view_id
        themes.append(
            ThemeView(
                id=view_id,
                name=item.get("name", ""),
                definition=item.get("definition", ""),
                scope=item.get("scope", ""),
                subthemes=tuple(item.get("subthemes", [])),
                technologies=tuple(item.get("technologies", [])),
                frequency_bands=tuple(item.get("frequency_bands", [])),
                countries_regions=tuple(item.get("countries_regions", [])),
                organizations=tuple(item.get("organizations", [])),
                finding_ids=tuple(item.get("finding_ids", [])),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                change_action=item.get("change_action", ""),
                confidence=item.get("confidence", ""),
                extraction_basis=item.get("extraction_basis", ""),
            )
        )

    trends: list[TrendView] = []
    for item in payload.get("trends", []):
        internal_id = _internal_id(item, "trend")
        trends.append(
            TrendView(
                id=public_id(
                    run_id, AnalysisStage.THEMATIC_LANDSCAPE, "trend", internal_id
                ),
                name=item.get("name", ""),
                description=item.get("description", ""),
                related_theme_ids=tuple(
                    theme_id_map.get(value, value)
                    for value in item.get("related_theme_temporary_ids", [])
                ),
                direction=item.get("direction", ""),
                time_horizon=item.get("time_horizon", ""),
                first_observed_date=item.get("first_observed_date"),
                latest_observed_date=item.get("latest_observed_date"),
                countries_regions=tuple(item.get("countries_regions", [])),
                organizations=tuple(item.get("organizations", [])),
                finding_ids=tuple(item.get("finding_ids", [])),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                confidence=item.get("confidence", ""),
            )
        )

    signals: list[EmergingSignalView] = []
    for item in payload.get("emerging_signals", []):
        internal_id = _internal_id(item, "signal")
        signals.append(
            EmergingSignalView(
                id=public_id(
                    run_id, AnalysisStage.THEMATIC_LANDSCAPE, "signal", internal_id
                ),
                title=item.get("title", ""),
                description=item.get("description", ""),
                novelty_explanation=item.get("novelty_explanation", ""),
                related_theme_ids=tuple(
                    theme_id_map.get(value, value)
                    for value in item.get("related_theme_temporary_ids", [])
                ),
                finding_ids=tuple(item.get("finding_ids", [])),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                confidence=item.get("confidence", ""),
            )
        )
    return tuple(themes), tuple(trends), tuple(signals), theme_id_map


def map_regulatory_intelligence(
    *, run_id: str, payload: Mapping[str, Any], theme_id_map: Mapping[str, str]
) -> tuple[tuple[RegulatoryIntelligenceView, ...], tuple[GapView, ...]]:
    intelligence: list[RegulatoryIntelligenceView] = []
    gaps: list[GapView] = []
    for item in payload.get("analyses", []):
        internal_id = _internal_id(item, "regulatory")
        theme_id = item.get("theme_id")
        if theme_id is None and item.get("theme_temporary_id") is not None:
            theme_id = theme_id_map.get(item["theme_temporary_id"])
        view_id = public_id(
            run_id, AnalysisStage.REGULATORY_INTELLIGENCE, "regulatory", internal_id
        )
        view = RegulatoryIntelligenceView(
            id=view_id,
            theme_id=theme_id,
            international_situation=item.get("international_situation", ""),
            regulatory_debate=item.get("regulatory_debate", ""),
            countries_regions=tuple(item.get("countries_regions", [])),
            organizations=tuple(item.get("organizations", [])),
            agenda_item_ids=tuple(item.get("agenda_item_ids", [])),
            relationship_type=item.get("relationship_type", ""),
            coverage_explanation=item.get("coverage_explanation", ""),
            implications_for_ane=item.get("implications_for_ane", ""),
            finding_ids=tuple(item.get("finding_ids", [])),
            evidence_ids=tuple(item.get("evidence_ids", [])),
            confidence=item.get("confidence", ""),
            extraction_basis=item.get("extraction_basis", ""),
        )
        intelligence.append(view)
        if view.relationship_type in GAP_RELATIONSHIP_TYPES:
            gaps.append(
                GapView(
                    id=public_id(
                        run_id,
                        AnalysisStage.REGULATORY_INTELLIGENCE,
                        "gap",
                        internal_id,
                    ),
                    relationship_type=view.relationship_type,
                    description=view.coverage_explanation,
                    theme_id=view.theme_id,
                    agenda_item_ids=view.agenda_item_ids,
                    finding_ids=view.finding_ids,
                    evidence_ids=view.evidence_ids,
                )
            )

    for index, description in enumerate(payload.get("overall_gaps", []), start=1):
        gaps.append(
            GapView(
                id=public_id(
                    run_id,
                    AnalysisStage.REGULATORY_INTELLIGENCE,
                    "gap",
                    f"overall-{index}",
                ),
                relationship_type="gap",
                description=str(description),
                theme_id=None,
                agenda_item_ids=(),
                finding_ids=(),
                evidence_ids=tuple(payload.get("evidence_ids", [])),
            )
        )
    return tuple(intelligence), tuple(gaps)


def map_strategic_assessment(
    *, run_id: str, payload: Mapping[str, Any]
) -> tuple[tuple[ImportanceView, ...], tuple[OpportunityView, ...], tuple[PmgeAlignmentView, ...]]:
    importance = []
    for item in payload.get("importance_assessments", []):
        _require_score(item, "importance_score")
        internal_id = _internal_id(item, "importance")
        importance.append(
            ImportanceView(
                id=public_id(
                    run_id,
                    AnalysisStage.STRATEGIC_ASSESSMENT,
                    "importance",
                    internal_id,
                ),
                subject_type=item.get("subject_type", ""),
                subject_id=item.get("subject_id", ""),
                dimensions=item.get("dimensions", {}),
                importance_score=item["importance_score"],
                level=item.get("level", ""),
                rationale=item.get("rationale", ""),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                confidence=item.get("confidence", ""),
            )
        )

    opportunities = []
    for item in payload.get("opportunity_assessments", []):
        _require_score(item, "opportunity_score")
        internal_id = _internal_id(item, "opportunity")
        opportunities.append(
            OpportunityView(
                id=public_id(
                    run_id,
                    AnalysisStage.STRATEGIC_ASSESSMENT,
                    "opportunity",
                    internal_id,
                ),
                theme_id=item.get("theme_id", ""),
                policy_activity_ids=tuple(item.get("policy_activity_ids", [])),
                dimensions=item.get("dimensions", {}),
                opportunity_score=item["opportunity_score"],
                level=item.get("level", ""),
                rationale=item.get("rationale", ""),
                suggested_action=item.get("suggested_action", ""),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                confidence=item.get("confidence", ""),
            )
        )

    alignments = []
    for item in payload.get("alignment_assessments", []):
        _require_score(item, "alignment_score")
        internal_id = _internal_id(item, "alignment")
        alignments.append(
            PmgeAlignmentView(
                id=public_id(
                    run_id,
                    AnalysisStage.STRATEGIC_ASSESSMENT,
                    "alignment",
                    internal_id,
                ),
                theme_id=item.get("theme_id", ""),
                pmge_project_ids=tuple(item.get("pmge_project_ids", [])),
                dimensions=item.get("dimensions", {}),
                alignment_score=item["alignment_score"],
                level=item.get("level", ""),
                rationale=item.get("rationale", ""),
                alignment_type=item.get("alignment_type", ""),
                evidence_ids=tuple(item.get("evidence_ids", [])),
                confidence=item.get("confidence", ""),
            )
        )
    return tuple(importance), tuple(opportunities), tuple(alignments)


def build_overview(
    *,
    themes: tuple[ThemeView, ...],
    trends: tuple[TrendView, ...],
    signals: tuple[EmergingSignalView, ...],
    regulatory: tuple[RegulatoryIntelligenceView, ...],
    gaps: tuple[GapView, ...],
    importance: tuple[ImportanceView, ...],
    opportunities: tuple[OpportunityView, ...],
    alignments: tuple[PmgeAlignmentView, ...],
) -> StrategicOverview:
    return StrategicOverview(
        theme_count=len(themes),
        trend_count=len(trends),
        emerging_signal_count=len(signals),
        regulatory_analysis_count=len(regulatory),
        gap_count=len(gaps),
        importance_count=len(importance),
        opportunity_count=len(opportunities),
        pmge_alignment_count=len(alignments),
        average_importance_score=_average(item.importance_score for item in importance),
        average_opportunity_score=_average(
            item.opportunity_score for item in opportunities
        ),
        average_alignment_score=_average(item.alignment_score for item in alignments),
    )


def _internal_id(item: Mapping[str, Any], entity_type: str) -> str:
    value = item.get("temporary_id") or item.get("id")
    if not value:
        raise DashboardMappingError(f"{entity_type} no tiene identificador interno.")
    return str(value)


def _require_score(item: Mapping[str, Any], field_name: str) -> None:
    if field_name not in item:
        raise DashboardMappingError(f"Assessment sin {field_name}.")


def _average(values: Iterable[float]) -> float | None:
    items = list(values)
    if not items:
        return None
    return round(sum(items) / len(items), 2)

