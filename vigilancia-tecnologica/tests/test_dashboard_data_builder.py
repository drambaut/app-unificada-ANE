"""Pruebas de la capa local de datos para la demo."""
from datetime import UTC, datetime
from pathlib import Path
import pandas as pd
import pytest
import app.dashboard_data_builder as builder
from app.topic_taxonomy import infer_tema_estrategico, normalize_bands, normalize_technologies, parse_list_field

def test_taxonomy_parses_and_normalizes_variants() -> None:
    assert parse_list_field('["WiFi", "Direct-to-Device"]') == ["WiFi", "Direct-to-Device"]
    assert normalize_technologies(["WiFi", "Artificial Intelligence"]) == ["Wi-Fi", "IA"]
    assert normalize_bands(["6 GHz superior", "Ka-band"]) == ["upper 6 GHz", "banda Ka"]
    assert infer_tema_estrategico(["NTN"], [], "") == "Conectividad satelital, NTN y D2D"


def test_extract_year_prefers_real_date_over_filename() -> None:
    assert builder._extract_year("2025-03-15") == "2025"
    assert builder._extract_year("March 2026") == "2026"
    assert builder._extract_year("") == ""
    # Con separadores claros si se reconoce como respaldo del nombre del archivo.
    assert builder._extract_year("Documento-Tendencias-2025.pdf") == "2025"
    # Sin limite de palabra claro (numero de referencia pegado), no se adivina.
    assert builder._extract_year("FLSPAR20250003_Enacom_reduces.pdf") == ""


def test_make_record_uses_document_date_for_year() -> None:
    row = pd.Series({
        "document_id": "1", "file_name": "reporte.pdf", "source_folder": "UIT",
        "tema_principal": "Consulta 6 GHz", "tecnologias": [], "bandas_frecuencia": [],
        "paises": [], "organizaciones": [], "actores": [], "palabras_clave": [],
        "relevancia_agenda_ane": "Media", "resumen": "", "justificacion_relevancia": "",
        "document_date": "2027-01-10",
    })
    record = builder._make_record(row)
    assert record["year"] == "2027"

def test_build_dashboard_data_creates_expected_demo_csvs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured = tmp_path / "outputs" / "structured_data"; demo = tmp_path / "demo_data"; structured.mkdir(parents=True)
    input_csv = structured / "structured_documents.csv"
    pd.DataFrame([{"document_id": "1", "file_name": "signal.pdf", "source_folder": "UIT", "file_type": "pdf", "tema_principal": "Consulta NTN", "tecnologias": '["Non-Terrestrial Networks", "WiFi"]', "bandas_frecuencia": '["6 GHz"]', "paises": '["Colombia"]', "organizaciones": '["UIT"]', "actores": '["Reguladores"]', "palabras_clave": '["consulta pública"]', "resumen": "Consulta sobre satélites", "relevancia_agenda_ane": "Alta", "justificacion_relevancia": "Prioridad ANE"}]).to_csv(input_csv, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(builder, "INPUT_CSV", input_csv); monkeypatch.setattr(builder, "STRUCTURED_DATA_DIR", structured); monkeypatch.setattr(builder, "DEMO_DATA_DIR", demo)
    result = builder.build_dashboard_data()
    assert result["records_processed"] == 1
    assert {path.name for path in demo.iterdir()} == set(builder.OUTPUT_NAMES)
    records = pd.read_csv(demo / "dashboard_records.csv")
    assert records.loc[0, "tema_estrategico"] == "Conectividad satelital, NTN y D2D"
    assert records.loc[0, "relevancia_score"] == 10
    assert records.loc[0, "actividad_internacional_score"] == 3

def test_missing_input_has_actionable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builder, "INPUT_CSV", tmp_path / "missing.csv")
    with pytest.raises(FileNotFoundError, match="python app/llm_extract.py"): builder.build_dashboard_data()


def test_load_provider_lookup_maps_file_name_to_provider(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([
        {"path": r"C:\corpus\Cullen International\report.pdf", "source_type": "surveillance", "provider": "Cullen International"},
        {"path": r"C:\corpus\GSMA\other.pdf", "source_type": "surveillance", "provider": "GSMA"},
    ]).to_csv(manifest, index=False)
    lookup = builder._load_provider_lookup(manifest)
    assert lookup == {"report.pdf": "Cullen International", "other.pdf": "GSMA"}


def test_load_provider_lookup_returns_empty_when_manifest_missing(tmp_path: Path) -> None:
    assert builder._load_provider_lookup(tmp_path / "missing.csv") == {}


def test_fetch_supabase_surveillance_source_maps_one_row_per_document_and_skips_other_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.documents.models import Document, DocumentStatus, SourceType
    from app.results.models import PersistenceBundle, ResultRecord

    surveillance_document = Document(
        id="doc-1", file_name="reporte.pdf", file_type="pdf", source_type=SourceType.SURVEILLANCE,
        file_hash="h1", storage_path="p1", document_date=None, status=DocumentStatus.PROCESSED,
        version=1, replaces_id=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    institutional_document = Document(
        id="doc-2", file_name="pmge.pdf", file_type="pdf", source_type=SourceType.INSTITUTIONAL_PLAN,
        file_hash="h2", storage_path="p2", document_date=None, status=DocumentStatus.PROCESSED,
        version=1, replaces_id=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )

    class FakeDocumentRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def list_processed_documents(self):
            return [surveillance_document, institutional_document]

    analysis_record = ResultRecord(
        id="rec-1", document_id="doc-1",
        data={
            "title": "Reporte", "summary": "Resumen del reporte",
            "preliminary_topics": ["NTN"], "technologies": ["NTN", "5G"],
            "frequency_bands": ["6 GHz"], "countries_regions": ["Colombia"],
            "organizations": ["UIT"], "actors": ["Reguladores"], "keywords": ["satelital"],
        },
        prompt_id="document_extraction", prompt_version="v1", contract_name="DocumentExtraction",
        model_name="gemini", created_at=datetime.now(UTC), canonical_key="k1", confidence="Alta",
    )
    bundle = PersistenceBundle(document_id="doc-1", document_analysis=analysis_record)

    class FakeResultRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def get_bundle(self, document_id: str):
            return bundle if document_id == "doc-1" else None

    import app.documents.supabase_repository as document_repository_module
    import app.results.supabase_repository as result_repository_module
    monkeypatch.setattr(document_repository_module, "SupabaseDocumentRepository", FakeDocumentRepository)
    monkeypatch.setattr(result_repository_module, "SupabaseResultRepository", FakeResultRepository)
    monkeypatch.setattr(builder, "MANIFEST_CSV", tmp_path / "missing_manifest.csv")

    source = builder._fetch_supabase_surveillance_source(settings=object())

    assert len(source) == 1
    row = source.iloc[0]
    assert row["document_id"] == "doc-1"
    assert row["file_name"] == "reporte.pdf"
    assert row["tecnologias"] == ["NTN", "5G"]
    assert row["bandas_frecuencia"] == ["6 GHz"]
    assert row["relevancia_agenda_ane"] == "Alta"
    assert row["resumen"] == "Resumen del reporte"


def test_fetch_supabase_surveillance_source_includes_previously_processed_documents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regresion: subir un documento nuevo no debe hacer desaparecer los anteriores.

    build_dashboard_data_from_supabase reconstruye demo_data consultando TODOS
    los documentos processed en Supabase, no solo el ultimo subido. Esta prueba
    fija ese contrato: dos documentos previamente procesados mas uno nuevo deben
    aparecer juntos en la fuente reconstruida.
    """
    from app.documents.models import Document, DocumentStatus, SourceType
    from app.results.models import PersistenceBundle, ResultRecord

    def _document(document_id: str, file_name: str) -> Document:
        return Document(
            id=document_id, file_name=file_name, file_type="pdf", source_type=SourceType.SURVEILLANCE,
            file_hash=f"hash-{document_id}", storage_path=f"path-{document_id}", document_date=None,
            status=DocumentStatus.PROCESSED, version=1, replaces_id=None,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )

    existing_documents = [_document("doc-1", "antiguo1.pdf"), _document("doc-2", "antiguo2.pdf")]
    newly_uploaded_document = _document("doc-3", "nuevo.pdf")

    class FakeDocumentRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def list_processed_documents(self):
            # Simula el estado real de Supabase DESPUES de subir un documento
            # nuevo: los ya procesados siguen ahi, mas el recien agregado.
            return [*existing_documents, newly_uploaded_document]

    def _bundle(document_id: str) -> PersistenceBundle:
        analysis = ResultRecord(
            id=f"rec-{document_id}", document_id=document_id,
            data={
                "title": document_id, "summary": f"Resumen {document_id}",
                "preliminary_topics": ["Seguimiento"], "technologies": [], "frequency_bands": [],
                "countries_regions": [], "organizations": [], "actors": [], "keywords": [],
            },
            prompt_id="document_extraction", prompt_version="v1", contract_name="DocumentExtraction",
            model_name="gemini", created_at=datetime.now(UTC), canonical_key=f"k-{document_id}", confidence="Media",
        )
        return PersistenceBundle(document_id=document_id, document_analysis=analysis)

    class FakeResultRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def get_bundle(self, document_id: str):
            return _bundle(document_id)

    import app.documents.supabase_repository as document_repository_module
    import app.results.supabase_repository as result_repository_module
    monkeypatch.setattr(document_repository_module, "SupabaseDocumentRepository", FakeDocumentRepository)
    monkeypatch.setattr(result_repository_module, "SupabaseResultRepository", FakeResultRepository)
    monkeypatch.setattr(builder, "MANIFEST_CSV", tmp_path / "missing_manifest.csv")

    source = builder._fetch_supabase_surveillance_source(settings=object())

    assert sorted(source["file_name"]) == ["antiguo1.pdf", "antiguo2.pdf", "nuevo.pdf"]


def test_regulatory_datasets_have_complete_explanations() -> None:
    records = pd.DataFrame([
        {"document_id": "1", "tema_estrategico": "6 GHz, Wi-Fi e IMT", "senal_regulatoria": "Consulta upper 6 GHz", "tecnologias": '["Wi-Fi"]', "bandas_frecuencia": '["6 GHz"]', "tipo_insumo_agenda": "Seguimiento", "relevancia_label": "Alta", "relevancia_score": 8},
        {"document_id": "2", "tema_estrategico": "Conectividad satelital, NTN y D2D", "senal_regulatoria": "Reglas D2D", "tecnologias": '["D2D"]', "bandas_frecuencia": '[]', "tipo_insumo_agenda": "Nota técnica", "relevancia_label": "Alta", "relevancia_score": 9},
    ])
    regulatory_map = builder.build_regulatory_map(records)
    trends = builder.build_regulatory_trends(records)
    assert len(trends) == regulatory_map["tema_macro"].nunique() == 2
    assert not regulatory_map[["subtema", "debate_regulatorio", "implicacion_regulatoria"]].replace("", pd.NA).isna().any().any()
    required = ["nombre_tendencia", "de_que_trata", "que_esta_pasando", "por_que_importa", "implicacion_regulatoria"]
    assert not trends[required].replace("", pd.NA).isna().any().any()


def test_policy_matrix_activities_are_generated_with_required_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "reference"
    reference.mkdir()
    pd.DataFrame([{
        "Documento": "Política de espectro",
        "Objetivo": "Uso eficiente del espectro",
        "Acción o Actividad": "Evaluar 6 GHz para Wi-Fi y uso libre",
        "Plazo ejecución": "2026",
        "Responsable": "ANE",
    }]).to_excel(reference / "matriz_politicas_publicas.xlsx", index=False)
    monkeypatch.setattr(builder, "REFERENCE_DATA_DIR", reference)
    activities = builder.build_policy_matrix_activities()
    assert list(activities.columns) == builder.POLICY_ACTIVITY_COLUMNS
    assert len(activities) == 1
    assert activities.loc[0, "activity_name"] == "Evaluar 6 GHz para Wi-Fi y uso libre"
    assert "6 GHz" in activities.loc[0, "keywords"]


def test_pmge_projects_fallback_empty_has_required_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "reference"
    reference.mkdir()
    monkeypatch.setattr(builder, "REFERENCE_DATA_DIR", reference)
    projects = builder.build_pmge_projects()
    assert list(projects.columns) == builder.PMGE_PROJECT_COLUMNS
    assert projects.empty


def test_alignment_outputs_columns_scores_values_and_support_documents() -> None:
    activities = pd.DataFrame([{
        "activity_id": "ACT-001", "policy_name": "Política de espectro", "instrument_name": "Política",
        "policy_axis": "Uso eficiente", "activity_name": "Evaluar 6 GHz para Wi-Fi",
        "activity_description": "Uso libre no licenciado en 6 GHz", "responsible_area": "ANE",
        "execution_period": "2026", "keywords": "6 GHz Wi-Fi uso libre",
    }])
    records = pd.DataFrame([{
        "document_id": "1", "file_name": "consulta-6ghz-2026.pdf", "source_folder": "CRC",
        "tema_estrategico": "6 GHz, Wi-Fi e IMT", "tipo_insumo_agenda": "Nota técnica",
    }])
    trends = pd.DataFrame([{
        "tema_macro": "6 GHz, Wi-Fi e IMT", "nombre_tendencia": "Uso libre de 6 GHz",
        "de_que_trata": "Wi-Fi y uso no licenciado", "que_esta_pasando": "Hay consultas sobre 6 GHz",
        "implicacion_regulatoria": "Definir condiciones", "relevancia_score_promedio": 9,
        "tipo_insumo_principal": "Nota técnica",
    }])
    document_alignment = builder.build_document_policy_alignment(trends, records, pd.DataFrame(), activities)
    assert list(document_alignment.columns) == builder.DOCUMENT_POLICY_ALIGNMENT_COLUMNS
    assert document_alignment.loc[0, "support_documents"] == "consulta-6ghz-2026.pdf"
    assert document_alignment["opportunity_score"].between(0, 100).all()
    assert set(document_alignment["coverage_status"]).issubset(set(builder.ALLOWED_COVERAGE_STATUS))
    projects = pd.DataFrame([{
        "project_id": "PMGE-001", "source_document": "pmge.pdf", "pmge_line": "Disponibilidad de espectro",
        "project_name": "Hoja de ruta 6 GHz", "project_description": "Wi-Fi y espectro no licenciado",
        "expected_output": "Hoja de ruta", "timeframe": "2026", "keywords": "6 GHz Wi-Fi uso libre",
    }])
    pmge_alignment = builder.build_pmge_policy_alignment(projects, activities)
    assert list(pmge_alignment.columns) == builder.PMGE_POLICY_ALIGNMENT_COLUMNS
    assert pmge_alignment["alignment_score"].between(0, 100).all()
    assert set(pmge_alignment["alignment_level"]).issubset(set(builder.ALLOWED_ALIGNMENT_LEVEL))


def test_fetch_supabase_pmge_projects_source_maps_persisted_projects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.documents.models import Document, DocumentStatus, SourceType
    from app.results.models import PersistenceBundle, ResultRecord

    institutional_document = Document(
        id="doc-pmge-1", file_name="pmge.pdf", file_type="pdf", source_type=SourceType.INSTITUTIONAL_PLAN,
        file_hash="h1", storage_path="p1", document_date=None, status=DocumentStatus.PROCESSED,
        version=1, replaces_id=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    surveillance_document = Document(
        id="doc-surv-1", file_name="reporte.pdf", file_type="pdf", source_type=SourceType.SURVEILLANCE,
        file_hash="h2", storage_path="p2", document_date=None, status=DocumentStatus.PROCESSED,
        version=1, replaces_id=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )

    class FakeDocumentRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def list_processed_documents(self):
            return [institutional_document, surveillance_document]

    project_record = ResultRecord(
        id="rec-project-1", document_id="doc-pmge-1",
        data={
            "project_name": "Hoja de ruta 6 GHz", "description": "Wi-Fi y espectro no licenciado",
            "objectives": ["Ampliar cobertura"], "activities": ["Consultar industria"],
            "expected_outputs": ["Hoja de ruta publicada"], "period": "2026-2028",
        },
        prompt_id="institutional_plan_extraction", prompt_version="v1",
        contract_name="InstitutionalPlanExtraction", model_name="gemini",
        created_at=datetime.now(UTC), canonical_key="k-project-1", confidence="Alta",
    )
    bundle = PersistenceBundle(document_id="doc-pmge-1", pmge_projects=[project_record])

    class FakeResultRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def get_bundle(self, document_id: str):
            return bundle if document_id == "doc-pmge-1" else None

    import app.documents.supabase_repository as document_repository_module
    import app.results.supabase_repository as result_repository_module
    monkeypatch.setattr(document_repository_module, "SupabaseDocumentRepository", FakeDocumentRepository)
    monkeypatch.setattr(result_repository_module, "SupabaseResultRepository", FakeResultRepository)

    source = builder._fetch_supabase_pmge_projects_source(settings=object())

    assert list(source.columns) == builder.PMGE_PROJECT_COLUMNS
    assert len(source) == 1
    row = source.iloc[0]
    assert row["project_name"] == "Hoja de ruta 6 GHz"
    assert row["source_document"] == "pmge.pdf"
    assert row["timeframe"] == "2026-2028"
    assert "Hoja de ruta publicada" in row["expected_output"]


def test_fetch_supabase_policy_matrix_activities_source_joins_activity_with_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.documents.models import Document, DocumentStatus, SourceType
    from app.results.models import PersistenceBundle, ResultRecord

    policy_matrix_document = Document(
        id="doc-policy-1", file_name="matriz.xlsx", file_type="xlsx", source_type=SourceType.POLICY_MATRIX,
        file_hash="h3", storage_path="p3", document_date=None, status=DocumentStatus.PROCESSED,
        version=1, replaces_id=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )

    class FakeDocumentRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def list_processed_documents(self):
            return [policy_matrix_document]

    policy_record = ResultRecord(
        id="rec-policy-1", document_id="doc-policy-1",
        data={
            "temporary_id": "policy-tmp-1", "policy_name": "Gestión eficiente del espectro",
            "instrument_name": "Plan estratégico", "policy_axis": "Innovación", "description": "Eje estratégico",
        },
        prompt_id="policy_matrix_extraction", prompt_version="v1", contract_name="PolicyMatrixExtraction",
        model_name="gemini", created_at=datetime.now(UTC), canonical_key="k-policy-1", confidence="Alta",
    )
    activity_record = ResultRecord(
        id="rec-activity-1", document_id="doc-policy-1",
        data={
            "policy_temporary_id": "policy-tmp-1", "activity_name": "Modernizar el monitoreo",
            "activity_description": "Actualizar herramientas de monitoreo del espectro",
            "responsible_area": "Subdirección técnica", "execution_period": "2026", "commitments": [],
            "keywords": ["monitoreo"],
        },
        prompt_id="policy_matrix_extraction", prompt_version="v1", contract_name="PolicyMatrixExtraction",
        model_name="gemini", created_at=datetime.now(UTC), canonical_key="k-activity-1", confidence="Alta",
    )
    bundle = PersistenceBundle(
        document_id="doc-policy-1", policies=[policy_record], policy_activities=[activity_record]
    )

    class FakeResultRepository:
        def __init__(self, *, settings=None) -> None:
            pass

        def get_bundle(self, document_id: str):
            return bundle if document_id == "doc-policy-1" else None

    import app.documents.supabase_repository as document_repository_module
    import app.results.supabase_repository as result_repository_module
    monkeypatch.setattr(document_repository_module, "SupabaseDocumentRepository", FakeDocumentRepository)
    monkeypatch.setattr(result_repository_module, "SupabaseResultRepository", FakeResultRepository)

    source = builder._fetch_supabase_policy_matrix_activities_source(settings=object())

    assert list(source.columns) == builder.POLICY_ACTIVITY_COLUMNS
    assert len(source) == 1
    row = source.iloc[0]
    assert row["policy_name"] == "Gestión eficiente del espectro"
    assert row["policy_axis"] == "Innovación"
    assert row["activity_name"] == "Modernizar el monitoreo"
    assert row["responsible_area"] == "Subdirección técnica"
