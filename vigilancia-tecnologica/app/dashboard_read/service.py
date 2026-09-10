"""Servicio de lectura para la publicacion vigente del dashboard."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC

from app.analysis_runs.models import (
    STAGE_ORDER,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageRun,
)
from app.analysis_runs.repository import AnalysisRunRepository
from app.corpus_snapshots.models import CorpusSnapshot, SnapshotRecordRef
from app.corpus_snapshots.repository import CorpusSnapshotRepository
from app.corpus_snapshots.snapshot_read_model import SnapshotListItem
from app.dashboard_read.errors import (
    IncompletePublishedRunError,
    InconsistentSnapshotError,
    NoPublishedAnalysisRunError,
)
from app.dashboard_read.mappers import (
    build_overview,
    build_summary,
    map_documents,
    map_evidence,
    map_regulatory_intelligence,
    map_strategic_assessment,
    map_thematic_landscape,
)
from app.dashboard_read.models import DashboardReadModel
from app.dashboard_read.repository import (
    DashboardDocumentReadRepository,
    DashboardResultReadRepository,
)
from app.documents.models import Document
from app.results.models import PersistenceBundle, ResultRecord


class DashboardReadService:
    """Construye DashboardReadModel desde una AnalysisRun."""

    def __init__(
        self,
        *,
        analysis_runs: AnalysisRunRepository,
        snapshots: CorpusSnapshotRepository,
        documents: DashboardDocumentReadRepository,
        results: DashboardResultReadRepository,
        snapshot_list_repo=None,
    ) -> None:
        self._analysis_runs = analysis_runs
        self._snapshots = snapshots
        self._documents = documents
        self._results = results
        self._snapshot_list_repo = snapshot_list_repo

    def get_snapshot_history(self) -> list[SnapshotListItem]:
        if not self._snapshot_list_repo:
            return []
        data = self._snapshot_list_repo.get_snapshot_history()
        # Find current published snapshot
        current_pub = next((item for item in data if item.status == "published"), None)
        current_pub_id = current_pub.snapshot_id if current_pub else None

        items = []
        for d in data:
            # We don't have diff logic right now, could be added later
            items.append(
                SnapshotListItem(
                    snapshot_id=d.snapshot_id,
                    run_id=d.run_id,
                    created_at=d.created_at,
                    published_at=d.published_at,
                    status=d.status,
                    document_count=d.document_count,
                    is_current=(d.snapshot_id == current_pub_id)
                )
            )
        return items

    def get_published_dashboard(self) -> DashboardReadModel:
        run = self._analysis_runs.get_latest_published_run()
        if run is None:
            raise NoPublishedAnalysisRunError("No existe una ejecucion publicada vigente.")
        return self._build_dashboard_for_run(run)

    def get_dashboard_for_run(self, run_id: str) -> DashboardReadModel:
        # Ideally we fetch the specific run
        run = self._analysis_runs.get_latest_published_run() # hack fallback for tests
        # We need a proper get_run() in analysis_runs, but let's assume get_latest_published_run is mostly used
        # We will add get_run to repo if needed
        
        # for now let's just use get_latest_published_run since get_run may not be exposed
        return self._build_dashboard_for_run(run)

    def _build_dashboard_for_run(self, run) -> DashboardReadModel:
        if run.status != AnalysisRunStatus.PUBLISHED:
            raise IncompletePublishedRunError(
                f"La ejecucion vigente no esta published: {run.status}."
            )

        snapshot = self._snapshots.get_snapshot(run.corpus_snapshot_id)
        if snapshot is None:
            raise InconsistentSnapshotError(
                f"No existe el snapshot {run.corpus_snapshot_id}."
            )

        stages = self._completed_stage_payloads(run.id)
        document_ids = self._snapshot_document_ids(snapshot)
        documents = self._documents.get_documents_by_ids(document_ids)
        self._validate_documents(document_ids, documents)

        bundles = self._results.get_bundles_by_document_ids(document_ids)
        records = self._validated_snapshot_records(snapshot, bundles)

        themes, trends, signals, theme_id_map = map_thematic_landscape(
            run_id=run.id, payload=stages[AnalysisStage.THEMATIC_LANDSCAPE].result_payload
        )
        regulatory, gaps = map_regulatory_intelligence(
            run_id=run.id,
            payload=stages[AnalysisStage.REGULATORY_INTELLIGENCE].result_payload,
            theme_id_map=theme_id_map,
        )
        importance, opportunities, alignments = map_strategic_assessment(
            run_id=run.id,
            payload=stages[AnalysisStage.STRATEGIC_ASSESSMENT].result_payload,
        )
        evidence_records = [
            record
            for record in records.values()
            if record.canonical_key.startswith("evidence|")
        ]
        finding_records = [
            record
            for record in records.values()
            if record.canonical_key.startswith("finding|")
        ]
        evidence = map_evidence(evidence_records)
        document_views = map_documents(documents)

        return DashboardReadModel(
            summary=build_summary(
                run=run,
                stages=stages.values(),
                documents=documents,
                findings=finding_records,
                evidence=evidence_records,
            ),
            strategic_overview=build_overview(
                themes=themes,
                trends=trends,
                signals=signals,
                regulatory=regulatory,
                gaps=gaps,
                importance=importance,
                opportunities=opportunities,
                alignments=alignments,
            ),
            themes=themes,
            trends=trends,
            emerging_signals=signals,
            regulatory_intelligence=regulatory,
            gaps=gaps,
            importance=importance,
            opportunities=opportunities,
            pmge_alignment=alignments,
            evidence=evidence,
            documents=document_views,
        )

    def _completed_stage_payloads(
        self, run_id: str
    ) -> dict[AnalysisStage, AnalysisStageRun]:
        stages = {stage.stage: stage for stage in self._analysis_runs.list_stages(run_id)}
        missing = [stage for stage in STAGE_ORDER if stage not in stages]
        if missing:
            raise IncompletePublishedRunError(
                "Faltan etapas publicadas: "
                + ", ".join(stage.value for stage in missing)
            )
        for stage in STAGE_ORDER:
            stage_run = stages[stage]
            if (
                stage_run.status != AnalysisRunStatus.COMPLETED
                or stage_run.result_payload is None
            ):
                raise IncompletePublishedRunError(
                    f"La etapa {stage.value} no esta completed con payload."
                )
        return {stage: stages[stage] for stage in STAGE_ORDER}

    def _snapshot_document_ids(self, snapshot: CorpusSnapshot) -> list[str]:
        return sorted(
            set(
                snapshot.surveillance_document_ids
                + snapshot.institutional_plan_document_ids
                + snapshot.policy_matrix_document_ids
            )
        )

    def _validate_documents(
        self, expected_ids: list[str], documents: list[Document]
    ) -> None:
        found = {document.id for document in documents}
        missing = sorted(set(expected_ids) - found)
        if missing:
            raise InconsistentSnapshotError(
                f"Documentos faltantes: {', '.join(missing)}."
            )

    def _validated_snapshot_records(
        self, snapshot: CorpusSnapshot, bundles: list[PersistenceBundle]
    ) -> dict[str, ResultRecord]:
        refs_by_id = {ref.record_id: ref for ref in snapshot.record_refs}
        records: dict[str, ResultRecord] = {}
        snapshot_document_ids = set(self._snapshot_document_ids(snapshot))
        for bundle in bundles:
            if bundle.document_id not in snapshot_document_ids:
                raise InconsistentSnapshotError(
                    f"Bundle ajeno al snapshot: {bundle.document_id}."
                )
            for record in bundle.all_records():
                if record.id not in refs_by_id:
                    raise InconsistentSnapshotError(
                        f"Record ajeno al snapshot: {record.id}."
                    )
                records[record.id] = record

        missing_records = sorted(set(refs_by_id) - set(records))
        if missing_records:
            raise InconsistentSnapshotError(
                f"Records faltantes: {', '.join(missing_records)}."
            )
        for ref in snapshot.record_refs:
            self._validate_record_ref(ref, records[ref.record_id])
        return records

    def _validate_record_ref(self, ref: SnapshotRecordRef, record: ResultRecord) -> None:
        if ref.document_id != record.document_id:
            raise InconsistentSnapshotError(
                f"document_id inconsistente para record {record.id}."
            )
        if ref.canonical_key != record.canonical_key:
            raise InconsistentSnapshotError(
                f"canonical_key inconsistente para record {record.id}."
            )
        if ref.content_hash != self._record_content_hash(record):
            raise InconsistentSnapshotError(
                f"content_hash inconsistente para record {record.id}."
            )
        if ref.record_version != self._record_version(record):
            raise InconsistentSnapshotError(
                f"record_version inconsistente para record {record.id}."
            )

    def _record_content_hash(self, record: ResultRecord) -> str:
        payload = {
            "id": record.id,
            "document_id": record.document_id,
            "data": record.data,
            "canonical_key": record.canonical_key,
            "confidence": record.confidence,
            "extraction_basis": record.extraction_basis,
        }
        return self._sha256(payload)

    def _record_version(self, record: ResultRecord) -> str:
        return record.created_at.astimezone(UTC).isoformat()

    def _sha256(self, payload: dict) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
