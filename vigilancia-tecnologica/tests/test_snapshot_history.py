from __future__ import annotations
import pytest
from datetime import UTC, datetime
from app.dashboard_read.service import DashboardReadService
from app.corpus_snapshots.snapshot_read_model import SnapshotListItem

class FakeSnapshotListRepository:
    def __init__(self, history=None):
        self.history = history or []

    def get_snapshot_history(self):
        return self.history

def test_get_snapshot_history_returns_history():
    history = [
        SnapshotListItem(
            snapshot_id="test-1",
            created_at="2026-01-01T00:00:00Z",
            published_at="2026-01-02T00:00:00Z",
            status="published",
            document_count=5
        ),
        SnapshotListItem(
            snapshot_id="test-2",
            created_at="2026-02-01T00:00:00Z",
            published_at=None,
            status="draft",
            document_count=10
        )
    ]
    repo = FakeSnapshotListRepository(history=history)
    service = DashboardReadService(
        analysis_runs=None,  # type: ignore
        snapshots=None,  # type: ignore
        documents=None,  # type: ignore
        results=None,  # type: ignore
        snapshot_list_repo=repo
    )
    
    result = service.get_snapshot_history()
    
    assert len(result) == 2
    assert result[0].snapshot_id == "test-1"
    assert result[1].snapshot_id == "test-2"

def test_get_snapshot_history_without_repo_returns_empty():
    service = DashboardReadService(
        analysis_runs=None,  # type: ignore
        snapshots=None,  # type: ignore
        documents=None,  # type: ignore
        results=None,  # type: ignore
        snapshot_list_repo=None
    )
    
    result = service.get_snapshot_history()
    
    assert result == []
