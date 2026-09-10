"""Modelos y constantes para scoring estrategico."""

from __future__ import annotations

from dataclasses import dataclass


IMPORTANCE_DIMENSIONS: tuple[str, ...] = (
    "ane_relevance",
    "magnitude",
    "urgency",
    "evidence_strength",
    "institutional_scope",
)

OPPORTUNITY_DIMENSIONS: tuple[str, ...] = (
    "policy_gap",
    "institutional_relevance",
    "actionability",
    "evidence_maturity",
    "timing",
)

ALIGNMENT_DIMENSIONS: tuple[str, ...] = (
    "objective_match",
    "activity_match",
    "deliverable_match",
    "temporal_match",
    "evidence_strength",
)


@dataclass(frozen=True)
class ScoreDefinition:
    collection_name: str
    dimensions: tuple[str, ...]
    score_field: str


STRATEGIC_SCORE_DEFINITIONS: tuple[ScoreDefinition, ...] = (
    ScoreDefinition(
        collection_name="importance_assessments",
        dimensions=IMPORTANCE_DIMENSIONS,
        score_field="importance_score",
    ),
    ScoreDefinition(
        collection_name="opportunity_assessments",
        dimensions=OPPORTUNITY_DIMENSIONS,
        score_field="opportunity_score",
    ),
    ScoreDefinition(
        collection_name="alignment_assessments",
        dimensions=ALIGNMENT_DIMENSIONS,
        score_field="alignment_score",
    ),
)

