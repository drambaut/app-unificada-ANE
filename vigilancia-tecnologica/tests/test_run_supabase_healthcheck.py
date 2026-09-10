"""Pruebas del smoke check Supabase."""

from dataclasses import dataclass

from app.analysis_runs.models import AnalysisRun, AnalysisRunStatus
from app.core.settings import load_settings
from run_supabase_healthcheck import collect_supabase_healthcheck, main


@dataclass(frozen=True)
class FakeDocument:
    id: str


class FakeDocuments:
    def __init__(self, count: int) -> None:
        self.count = count

    def list_processed_documents(self):
        return [FakeDocument(str(index)) for index in range(self.count)]


class FakeAnalysisRuns:
    def __init__(self, run: AnalysisRun | None) -> None:
        self.run = run

    def get_latest_published_run(self):
        return self.run


class FakeStorage:
    def __init__(self, buckets) -> None:
        self._buckets = buckets

    def list_buckets(self):
        return self._buckets


class FakeClient:
    def __init__(self, buckets) -> None:
        self.storage = FakeStorage(buckets)


def _settings():
    return load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-key",
            "SUPABASE_STORAGE_BUCKET": "source-documents",
        }
    )


def _run() -> AnalysisRun:
    return AnalysisRun(
        id="run-1",
        corpus_snapshot_id="snapshot-1",
        status=AnalysisRunStatus.PUBLISHED,
        attempts=1,
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
        updated_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
        started_at=None,
        completed_at=None,
        published_at=None,
        failed_at=None,
        error_message=None,
    )


def test_collect_supabase_healthcheck_reports_ready_strict_state():
    result = collect_supabase_healthcheck(
        settings=_settings(),
        document_repository=FakeDocuments(2),
        analysis_run_repository=FakeAnalysisRuns(_run()),
        client=FakeClient([{"id": "source-documents"}]),
    )

    assert result.connectivity_ok is True
    assert result.strict_ok is True
    assert result.processed_document_count == 2
    assert result.published_run_id == "run-1"


def test_collect_supabase_healthcheck_non_strict_allows_empty_publication_state():
    result = collect_supabase_healthcheck(
        settings=_settings(),
        document_repository=FakeDocuments(0),
        analysis_run_repository=FakeAnalysisRuns(None),
        client=FakeClient([{"name": "source-documents"}]),
    )

    assert result.connectivity_ok is True
    assert result.strict_ok is False
    assert result.processed_document_count == 0
    assert result.published_run_id is None


def test_main_strict_fails_when_not_fully_ready(monkeypatch, capsys):
    def fake_collect():
        return collect_supabase_healthcheck(
            settings=_settings(),
            document_repository=FakeDocuments(0),
            analysis_run_repository=FakeAnalysisRuns(None),
            client=FakeClient([{"id": "source-documents"}]),
        )

    monkeypatch.setattr("run_supabase_healthcheck.collect_supabase_healthcheck", fake_collect)

    assert main(["--strict"]) == 1
    assert "Strict mode: FAIL" in capsys.readouterr().out
