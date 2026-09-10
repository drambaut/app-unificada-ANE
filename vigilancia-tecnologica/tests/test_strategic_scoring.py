"""Pruebas del scoring matematico de StrategicAssessment."""

from __future__ import annotations

import copy

import pytest

from app.scoring.errors import InvalidScoringDimensionsError
from app.scoring.strategic import score_strategic_assessment


def importance_dimensions(value=5):
    return {
        "ane_relevance": value,
        "magnitude": value,
        "urgency": value,
        "evidence_strength": value,
        "institutional_scope": value,
    }


def opportunity_dimensions(value=5):
    return {
        "policy_gap": value,
        "institutional_relevance": value,
        "actionability": value,
        "evidence_maturity": value,
        "timing": value,
    }


def alignment_dimensions(value=5):
    return {
        "objective_match": value,
        "activity_match": value,
        "deliverable_match": value,
        "temporal_match": value,
        "evidence_strength": value,
    }


def assessment(dimensions: dict, **extra):
    base = {
        "temporary_id": "assessment-1",
        "dimensions": dimensions,
        "level": "Alta",
        "rationale": "Razon",
        "evidence_ids": ["ev-1"],
        "confidence": "Alta",
    }
    base.update(extra)
    return base


def payload():
    return {
        "importance_assessments": [
            assessment(
                importance_dimensions(5),
                subject_type="theme",
                subject_id="theme-1",
            )
        ],
        "opportunity_assessments": [
            assessment(
                opportunity_dimensions(2.5),
                theme_id="theme-1",
                policy_activity_ids=["policy-activity-1"],
                suggested_action="Accion",
            )
        ],
        "alignment_assessments": [
            assessment(
                alignment_dimensions(0),
                theme_id="theme-1",
                pmge_project_ids=["project-1"],
                alignment_type="partial",
            )
        ],
    }


def test_scores_zero_fifty_and_hundred():
    scored = score_strategic_assessment(payload())

    assert scored["importance_assessments"][0]["importance_score"] == 100.00
    assert scored["opportunity_assessments"][0]["opportunity_score"] == 50.00
    assert scored["alignment_assessments"][0]["alignment_score"] == 0.00


def test_decimal_values_are_rounded_to_two_decimals():
    data = {
        "importance_assessments": [
            assessment(
                {
                    "ane_relevance": 1,
                    "magnitude": 2,
                    "urgency": 3,
                    "evidence_strength": 4,
                    "institutional_scope": 5,
                }
            )
        ],
        "opportunity_assessments": [
            assessment(
                {
                    "policy_gap": 0.1,
                    "institutional_relevance": 0.2,
                    "actionability": 0.3,
                    "evidence_maturity": 0.4,
                    "timing": 0.5,
                }
            )
        ],
        "alignment_assessments": [],
    }

    scored = score_strategic_assessment(data)

    assert scored["importance_assessments"][0]["importance_score"] == 60.00
    assert scored["opportunity_assessments"][0]["opportunity_score"] == 6.00


def test_calculates_three_collections_separately():
    scored = score_strategic_assessment(payload())

    assert "importance_score" in scored["importance_assessments"][0]
    assert "opportunity_score" in scored["opportunity_assessments"][0]
    assert "alignment_score" in scored["alignment_assessments"][0]
    assert "opportunity_score" not in scored["importance_assessments"][0]


def test_rejects_missing_dimensions():
    data = payload()
    del data["importance_assessments"][0]["dimensions"]["urgency"]

    with pytest.raises(InvalidScoringDimensionsError, match="urgency"):
        score_strategic_assessment(data)


def test_rejects_additional_dimensions():
    data = payload()
    data["opportunity_assessments"][0]["dimensions"]["extra"] = 3

    with pytest.raises(InvalidScoringDimensionsError, match="extra"):
        score_strategic_assessment(data)


@pytest.mark.parametrize("value", [-1, 6, "5", None, object()])
def test_rejects_invalid_values(value):
    data = payload()
    data["alignment_assessments"][0]["dimensions"]["objective_match"] = value

    with pytest.raises(InvalidScoringDimensionsError):
        score_strategic_assessment(data)


def test_rejects_booleans():
    data = payload()
    data["importance_assessments"][0]["dimensions"]["ane_relevance"] = True

    with pytest.raises(InvalidScoringDimensionsError, match="ane_relevance"):
        score_strategic_assessment(data)


def test_payload_original_stays_intact():
    data = payload()
    original = copy.deepcopy(data)

    score_strategic_assessment(data)

    assert data == original


def test_original_fields_are_preserved():
    data = payload()
    scored = score_strategic_assessment(data)

    item = scored["importance_assessments"][0]
    assert item["temporary_id"] == "assessment-1"
    assert item["rationale"] == "Razon"
    assert item["evidence_ids"] == ["ev-1"]
    assert item["confidence"] == "Alta"
    assert item["subject_id"] == "theme-1"


def test_result_is_deterministic():
    data = payload()

    assert score_strategic_assessment(data) == score_strategic_assessment(data)


def test_empty_lists_are_valid():
    scored = score_strategic_assessment(
        {
            "importance_assessments": [],
            "opportunity_assessments": [],
            "alignment_assessments": [],
        }
    )

    assert scored == {
        "importance_assessments": [],
        "opportunity_assessments": [],
        "alignment_assessments": [],
    }
