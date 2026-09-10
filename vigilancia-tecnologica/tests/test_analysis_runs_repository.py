"""Pruebas del repositorio de ejecuciones de analisis transversal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analysis_runs.errors import (
    ConcurrentAnalysisRunError,
    IncompleteAnalysisPublicationError,
    InvalidAnalysisRetryError,
    InvalidAnalysisTransitionError,
)
from app.analysis_runs.in_memory_repository import InMemoryAnalysisRunRepository
from app.analysis_runs.models import AnalysisRunStatus, AnalysisStage


def uuid_factory():
    counter = {"value": 0}

    def next_uuid() -> str:
        counter["value"] += 1
        return f"uuid-{counter['value']}"

    return next_uuid


def clock_factory():
    current = {"value": datetime(2026, 1, 1, tzinfo=UTC)}

    def now() -> datetime:
        value = current["value"]
        current["value"] = value + timedelta(seconds=1)
        return value

    return now


@pytest.fixture
def repository() -> InMemoryAnalysisRunRepository:
    return InMemoryAnalysisRunRepository(
        uuid_factory=uuid_factory(), clock=clock_factory()
    )


def start_and_complete_stage(
    repository: InMemoryAnalysisRunRepository,
    run_id: str,
    stage: AnalysisStage,
) -> None:
    repository.update_stage_status(run_id, stage, AnalysisRunStatus.RUNNING)
    repository.save_stage_result(run_id, stage, {"stage": stage.value})
    repository.update_stage_status(run_id, stage, AnalysisRunStatus.COMPLETED)


def complete_run(repository: InMemoryAnalysisRunRepository, run_id: str) -> None:
    repository.update_run_status(run_id, AnalysisRunStatus.RUNNING)
    for stage in (
        AnalysisStage.THEMATIC_LANDSCAPE,
        AnalysisStage.REGULATORY_INTELLIGENCE,
        AnalysisStage.STRATEGIC_ASSESSMENT,
    ):
        start_and_complete_stage(repository, run_id, stage)
    repository.update_run_status(run_id, AnalysisRunStatus.COMPLETED)


def test_creates_run_with_three_ordered_stages(repository):
    run = repository.create_run("snapshot-1")

    assert run.corpus_snapshot_id == "snapshot-1"
    assert run.status == AnalysisRunStatus.QUEUED
    assert run.attempts == 0

    stages = repository.list_stages(run.id)
    assert [stage.stage for stage in stages] == [
        AnalysisStage.THEMATIC_LANDSCAPE,
        AnalysisStage.REGULATORY_INTELLIGENCE,
        AnalysisStage.STRATEGIC_ASSESSMENT,
    ]
    assert [stage.status for stage in stages] == [AnalysisRunStatus.QUEUED] * 3


def test_prompt_and_contract_values_are_frozen_at_creation(repository):
    run = repository.create_run("snapshot-1")
    stages = repository.list_stages(run.id)

    assert stages[0].prompt_id == "thematic_landscape"
    assert stages[0].prompt_version == "v1"
    assert stages[0].contract_name == "ThematicLandscape"
    assert stages[1].prompt_id == "regulatory_intelligence"
    assert stages[1].contract_name == "RegulatoryIntelligence"
    assert stages[2].prompt_id == "strategic_assessment"
    assert stages[2].contract_name == "StrategicAssessment"


def test_valid_transitions_and_attempts(repository):
    run = repository.create_run("snapshot-1")

    running_run = repository.update_run_status(run.id, AnalysisRunStatus.RUNNING)
    assert running_run.status == AnalysisRunStatus.RUNNING
    assert running_run.attempts == 1
    assert running_run.started_at is not None

    stage = repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
    )
    assert stage.status == AnalysisRunStatus.RUNNING
    assert stage.attempts == 1

    completed_stage = repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.COMPLETED
    )
    assert completed_stage.completed_at is not None


def test_invalid_transitions_are_rejected_without_mutation(repository):
    run = repository.create_run("snapshot-1")
    before = repository.get_run(run.id)

    with pytest.raises(InvalidAnalysisTransitionError):
        repository.update_run_status(run.id, AnalysisRunStatus.COMPLETED)

    assert repository.get_run(run.id) == before

    stage_before = repository.get_stage(run.id, AnalysisStage.THEMATIC_LANDSCAPE)
    with pytest.raises(InvalidAnalysisTransitionError):
        repository.update_stage_status(
            run.id,
            AnalysisStage.THEMATIC_LANDSCAPE,
            AnalysisRunStatus.COMPLETED,
        )
    assert repository.get_stage(run.id, AnalysisStage.THEMATIC_LANDSCAPE) == stage_before


def test_rejects_concurrent_run_for_same_snapshot(repository):
    repository.create_run("snapshot-1")

    with pytest.raises(ConcurrentAnalysisRunError):
        repository.create_run("snapshot-1")


def test_allows_new_run_after_previous_snapshot_run_is_failed(repository):
    first = repository.create_run("snapshot-1")
    repository.update_run_status(first.id, AnalysisRunStatus.RUNNING)
    repository.update_run_status(
        first.id, AnalysisRunStatus.FAILED, error_message="fallo"
    )

    second = repository.create_run("snapshot-1")

    assert second.id != first.id


def test_save_stage_result_uses_copy(repository):
    run = repository.create_run("snapshot-1")
    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
    )
    payload = {"items": [{"name": "tema"}]}

    saved = repository.save_stage_result(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, payload
    )
    payload["items"][0]["name"] = "mutado"

    assert saved.result_payload == {"items": [{"name": "tema"}]}
    assert repository.get_stage(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE
    ).result_payload == {"items": [{"name": "tema"}]}


def test_rejects_repeating_completed_or_running_stage(repository):
    run = repository.create_run("snapshot-1")
    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
    )

    with pytest.raises(InvalidAnalysisTransitionError):
        repository.update_stage_status(
            run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
        )

    repository.update_stage_status(
        run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.COMPLETED
    )

    with pytest.raises(InvalidAnalysisTransitionError):
        repository.update_stage_status(
            run.id, AnalysisStage.THEMATIC_LANDSCAPE, AnalysisRunStatus.RUNNING
        )


def test_retry_failed_stage_and_invalidates_later_stages(repository):
    run = repository.create_run("snapshot-1")
    start_and_complete_stage(
        repository, run.id, AnalysisStage.THEMATIC_LANDSCAPE
    )
    repository.update_stage_status(
        run.id, AnalysisStage.REGULATORY_INTELLIGENCE, AnalysisRunStatus.RUNNING
    )
    repository.update_stage_status(
        run.id,
        AnalysisStage.REGULATORY_INTELLIGENCE,
        AnalysisRunStatus.FAILED,
        error_message="fallo regulatorio",
    )
    later = repository.get_stage(run.id, AnalysisStage.STRATEGIC_ASSESSMENT)

    stages = repository.prepare_stage_retry(
        run.id, AnalysisStage.REGULATORY_INTELLIGENCE
    )

    thematic = stages[0]
    retried = stages[1]
    invalidated = stages[2]
    assert thematic.status == AnalysisRunStatus.COMPLETED
    assert thematic.result_payload == {"stage": "thematic_landscape"}
    assert retried.status == AnalysisRunStatus.QUEUED
    assert retried.error_message is None
    assert retried.result_payload is None
    assert retried.attempts == 1
    assert invalidated.status == AnalysisRunStatus.QUEUED
    assert invalidated.started_at is None
    assert invalidated.completed_at is None
    assert invalidated.failed_at is None
    assert invalidated.result_payload is None
    assert later.id == invalidated.id


def test_retry_requires_failed_stage(repository):
    run = repository.create_run("snapshot-1")
    before = repository.list_stages(run.id)

    with pytest.raises(InvalidAnalysisRetryError):
        repository.prepare_stage_retry(run.id, AnalysisStage.THEMATIC_LANDSCAPE)

    assert repository.list_stages(run.id) == before


def test_publish_completed_run(repository):
    run = repository.create_run("snapshot-1")
    complete_run(repository, run.id)

    published = repository.publish_run(run.id)

    assert published.status == AnalysisRunStatus.PUBLISHED
    assert published.published_at is not None
    assert repository.get_latest_published_run() == published


def test_rejects_incomplete_publication_without_mutation(repository):
    run = repository.create_run("snapshot-1")
    before = repository.get_run(run.id)

    with pytest.raises(IncompleteAnalysisPublicationError):
        repository.publish_run(run.id)

    assert repository.get_run(run.id) == before
    assert repository.get_latest_published_run() is None


def test_replaces_latest_published_run_atomically_and_preserves_history(repository):
    first = repository.create_run("snapshot-1")
    complete_run(repository, first.id)
    first_published = repository.publish_run(first.id)

    second = repository.create_run("snapshot-2")
    complete_run(repository, second.id)
    second_published = repository.publish_run(second.id)

    assert repository.get_latest_published_run() == second_published
    assert repository.get_run(first.id) == first_published
    assert repository.get_run(first.id).status == AnalysisRunStatus.PUBLISHED


def test_failed_publication_does_not_replace_current_publication(repository):
    first = repository.create_run("snapshot-1")
    complete_run(repository, first.id)
    first_published = repository.publish_run(first.id)

    incomplete = repository.create_run("snapshot-2")
    with pytest.raises(IncompleteAnalysisPublicationError):
        repository.publish_run(incomplete.id)

    assert repository.get_latest_published_run() == first_published
    assert repository.get_run(incomplete.id).status == AnalysisRunStatus.QUEUED
