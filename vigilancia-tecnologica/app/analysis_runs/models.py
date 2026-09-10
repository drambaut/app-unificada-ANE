"""Modelos inmutables para ejecuciones del analisis transversal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AnalysisRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"


class AnalysisStage(str, Enum):
    THEMATIC_LANDSCAPE = "thematic_landscape"
    REGULATORY_INTELLIGENCE = "regulatory_intelligence"
    STRATEGIC_ASSESSMENT = "strategic_assessment"


@dataclass(frozen=True)
class StagePromptSpec:
    prompt_id: str
    prompt_version: str
    contract_name: str


STAGE_ORDER: tuple[AnalysisStage, ...] = (
    AnalysisStage.THEMATIC_LANDSCAPE,
    AnalysisStage.REGULATORY_INTELLIGENCE,
    AnalysisStage.STRATEGIC_ASSESSMENT,
)


DEFAULT_STAGE_PROMPTS: dict[AnalysisStage, StagePromptSpec] = {
    AnalysisStage.THEMATIC_LANDSCAPE: StagePromptSpec(
        prompt_id="thematic_landscape",
        prompt_version="v1",
        contract_name="ThematicLandscape",
    ),
    AnalysisStage.REGULATORY_INTELLIGENCE: StagePromptSpec(
        prompt_id="regulatory_intelligence",
        prompt_version="v1",
        contract_name="RegulatoryIntelligence",
    ),
    AnalysisStage.STRATEGIC_ASSESSMENT: StagePromptSpec(
        prompt_id="strategic_assessment",
        prompt_version="v1",
        contract_name="StrategicAssessment",
    ),
}


@dataclass(frozen=True)
class AnalysisRun:
    id: str
    # Referencia estable a una instantanea futura del corpus: documentos,
    # findings, evidencias y referentes institucionales incluidos.
    corpus_snapshot_id: str
    status: AnalysisRunStatus
    attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    published_at: datetime | None
    failed_at: datetime | None
    error_message: str | None


@dataclass(frozen=True)
class AnalysisStageRun:
    id: str
    analysis_run_id: str
    stage: AnalysisStage
    status: AnalysisRunStatus
    prompt_id: str
    prompt_version: str
    contract_name: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    error_message: str | None
    result_payload: dict | None

