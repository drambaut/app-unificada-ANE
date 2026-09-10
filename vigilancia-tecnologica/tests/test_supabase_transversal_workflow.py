"""Pruebas del workflow transversal alimentado desde Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from app.analysis_runs.models import AnalysisRunStatus
from app.documents.models import Document, DocumentStatus, SourceType
from app.results.models import PersistenceBundle
from app.workflows.supabase_transversal import (
    SupabaseTransversalAnalysisWorkflow,
    SupabaseTransversalAnalysisWorkflowError,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def document(document_id: str, source_type: SourceType) -> Document:
    return Document(
        id=document_id,
        file_name=f"{document_id}.pdf",
        file_type="pdf",
        source_type=source_type,
        file_hash=f"hash-{document_id}",
        storage_path=f"{source_type.value}/{document_id}/{document_id}.pdf",
        document_date=date(2026, 1, 1),
        status=DocumentStatus.PROCESSED,
        version=1,
        replaces_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


@dataclass(frozen=True)
class FakeRun:
    status: AnalysisRunStatus


@dataclass(frozen=True)
class FakeTransversalResult:
    run: FakeRun


class FakeDocumentRepository:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    def list_processed_documents(self):
        return self.documents


class FakeResultRepository:
    def __init__(self, bundles: dict[str, PersistenceBundle]) -> None:
        self.bundles = bundles
        self.requested_ids: list[str] = []

    def get_bundle(self, document_id: str):
        self.requested_ids.append(document_id)
        return self.bundles.get(document_id)


class FakeTransversalWorkflow:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(
        self,
        *,
        documents,
        bundles,
        selection_criteria=None,
        metadata=None,
        auto_publish=True,
    ):
        self.calls.append(
            {
                "documents": documents,
                "bundles": bundles,
                "selection_criteria": selection_criteria,
                "metadata": metadata,
                "auto_publish": auto_publish,
            }
        )
        return FakeTransversalResult(run=FakeRun(status=AnalysisRunStatus.PUBLISHED))


def test_loads_processed_documents_and_bundles_before_running_transversal_analysis():
    docs = [
        document("doc-surv", SourceType.SURVEILLANCE),
        document("doc-plan", SourceType.INSTITUTIONAL_PLAN),
        document("doc-policy", SourceType.POLICY_MATRIX),
    ]
    bundles = {doc.id: PersistenceBundle(document_id=doc.id) for doc in docs}
    result_repository = FakeResultRepository(bundles)
    transversal = FakeTransversalWorkflow()
    workflow = SupabaseTransversalAnalysisWorkflow(
        document_repository=FakeDocumentRepository(docs),
        result_repository=result_repository,
        transversal_workflow=transversal,
    )

    result = workflow.run(
        selection_criteria={"cutoff": "2026-01-01"},
        metadata={"requested_by": "test"},
    )

    assert result.run.status == AnalysisRunStatus.PUBLISHED
    assert result_repository.requested_ids == ["doc-surv", "doc-plan", "doc-policy"]
    assert transversal.calls == [
        {
            "documents": docs,
            "bundles": list(bundles.values()),
            "selection_criteria": {
                "status": "processed",
                "cutoff": "2026-01-01",
            },
            "metadata": {"requested_by": "test"},
            "auto_publish": True,
        }
    ]


def test_rejects_processed_document_without_persisted_bundle():
    docs = [document("doc-surv", SourceType.SURVEILLANCE)]
    workflow = SupabaseTransversalAnalysisWorkflow(
        document_repository=FakeDocumentRepository(docs),
        result_repository=FakeResultRepository({}),
        transversal_workflow=FakeTransversalWorkflow(),
    )

    with pytest.raises(
        SupabaseTransversalAnalysisWorkflowError,
        match="doc-surv",
    ):
        workflow.run()


def test_rejects_empty_processed_corpus_before_running_transversal_workflow():
    transversal = FakeTransversalWorkflow()
    workflow = SupabaseTransversalAnalysisWorkflow(
        document_repository=FakeDocumentRepository([]),
        result_repository=FakeResultRepository({}),
        transversal_workflow=transversal,
    )

    with pytest.raises(
        SupabaseTransversalAnalysisWorkflowError,
        match="No hay documentos processed",
    ):
        workflow.run()

    assert transversal.calls == []
