"""Scoring matematico para StrategicAssessment."""

from __future__ import annotations

import copy
from numbers import Real
from typing import Any

from app.scoring.errors import InvalidScoringDimensionsError
from app.scoring.models import STRATEGIC_SCORE_DEFINITIONS, ScoreDefinition


def score_strategic_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    """Devuelve una copia del payload con scores 0-100 por assessment."""

    scored = copy.deepcopy(payload)
    for definition in STRATEGIC_SCORE_DEFINITIONS:
        assessments = scored.get(definition.collection_name, [])
        if not isinstance(assessments, list):
            raise InvalidScoringDimensionsError(
                f"{definition.collection_name} debe ser una lista."
            )
        for index, assessment in enumerate(assessments):
            if not isinstance(assessment, dict):
                raise InvalidScoringDimensionsError(
                    f"{definition.collection_name}[{index}] debe ser un objeto."
                )
            dimensions = assessment.get("dimensions")
            assessment[definition.score_field] = calculate_score(
                dimensions,
                definition=definition,
                path=f"{definition.collection_name}[{index}].dimensions",
            )
    return scored


def calculate_score(
    dimensions: dict[str, Any] | None,
    *,
    definition: ScoreDefinition,
    path: str,
) -> float:
    """Calcula round((suma / (cantidad * 5)) * 100, 2)."""

    if not isinstance(dimensions, dict):
        raise InvalidScoringDimensionsError(f"{path} debe ser un objeto.")

    expected = set(definition.dimensions)
    actual = set(dimensions)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise InvalidScoringDimensionsError(
            f"{path} no contiene dimensiones requeridas: {', '.join(missing)}."
        )
    if extra:
        raise InvalidScoringDimensionsError(
            f"{path} contiene dimensiones no soportadas: {', '.join(extra)}."
        )

    values: list[float] = []
    for dimension in definition.dimensions:
        value = dimensions[dimension]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise InvalidScoringDimensionsError(
                f"{path}.{dimension} debe ser numerico entre 0 y 5."
            )
        if value < 0 or value > 5:
            raise InvalidScoringDimensionsError(
                f"{path}.{dimension} esta fuera del rango 0-5."
            )
        values.append(float(value))

    return round((sum(values) / (len(definition.dimensions) * 5)) * 100, 2)

