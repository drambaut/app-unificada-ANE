"""Pruebas del servicio LLM modular sin llamadas reales."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.settings import (
    DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
    DEFAULT_STORAGE_ALLOWED_MIME_TYPES,
    DEFAULT_STORAGE_BUCKET,
    DEFAULT_STORAGE_FILE_SIZE_LIMIT_BYTES,
    Settings,
)
from app.documents.models import DocumentChunk
from app.llm.base import LLMInput
from app.llm.errors import (
    EmptyLLMResponseError,
    InvalidLLMJSONError,
    LLMProviderError,
    MissingConfigurationError,
)
from app.llm.gemini_client import GeminiStructuredClient
from app.llm.input_builder import build_excel_input, build_pdf_input
from app.llm.service import StructuredExtractionService


def evidence() -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": "Texto fuente.",
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": "Seccion",
        "confidence": "Alta",
    }


def document_payload(confidence: str = "Alta") -> dict:
    return {
        "document_analysis": {
            "temporary_id": "analysis-1",
            "document_type": "reporte",
            "title": "Documento",
            "summary": "Resumen",
            "preliminary_topics": [],
            "technologies": [],
            "frequency_bands": [],
            "countries_regions": [],
            "organizations": [],
            "actors": [],
            "keywords": [],
            "confidence": "Alta",
            "extraction_basis": "explicit",
            "evidence_ids": ["ev-1"],
        },
        "findings": [
            {
                "temporary_id": "finding-1",
                "finding_type": "estudio_o_evidencia",
                "title": "Hallazgo",
                "description": "Descripcion",
                "preliminary_topics": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
                "confidence": confidence,
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [],
        "objectives": [],
        "activities": [],
        "regulatory_agenda_initiatives": [],
        "regulatory_agenda_deliverables": [],
        "evidence": [],
    }


def policy_payload() -> dict:
    return {
        "policies": [],
        "activities": [],
        "commitments": [],
        "evidence": [],
    }


def thematic_payload(change_action: str = "create") -> dict:
    return {
        "corpus_summary": "Resumen.",
        "themes": [
            {
                "temporary_id": "theme-1",
                "name": "Tema abierto",
                "definition": "Definicion",
                "scope": "Alcance",
                "subthemes": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
                "finding_ids": ["finding-uuid"],
                "evidence_ids": ["ev-uuid"],
                "change_action": change_action,
                "previous_topic_ids": [],
                "confidence": "Alta",
                "extraction_basis": "mixed",
            }
        ],
        "trends": [],
        "emerging_signals": [],
        "evidence_ids": ["ev-uuid"],
    }


def regulatory_payload() -> dict:
    return {
        "analyses": [
            {
                "temporary_id": "reg-1",
                "theme_id": "theme-uuid",
                "international_situation": "Situacion",
                "regulatory_debate": "Debate",
                "countries_regions": [],
                "organizations": [],
                "agenda_item_ids": ["agenda-uuid"],
                "relationship_type": "covered",
                "coverage_explanation": "Cubierto",
                "implications_for_ane": "Implicaciones",
                "finding_ids": ["finding-uuid"],
                "evidence_ids": ["ev-uuid"],
                "confidence": "Alta",
                "extraction_basis": "explicit",
            }
        ],
        "overall_gaps": [],
        "evidence_ids": ["ev-uuid"],
    }


def strategic_payload() -> dict:
    return {
        "importance_assessments": [
            {
                "temporary_id": "importance-1",
                "subject_type": "theme",
                "subject_id": "theme-uuid",
                "dimensions": {
                    "ane_relevance": 5,
                    "magnitude": 4,
                    "urgency": 3,
                    "evidence_strength": 4,
                    "institutional_scope": 5,
                },
                "level": "Alta",
                "rationale": "Razon",
                "evidence_ids": ["ev-uuid"],
                "confidence": "Alta",
            }
        ],
        "opportunity_assessments": [],
        "alignment_assessments": [],
    }


class FakeClient:
    model_name = "fake-model"

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or document_payload()
        self.calls: list[dict] = []

    def generate_json(
        self, *, prompt: str, input_data: LLMInput, response_schema: dict
    ) -> dict:
        self.calls.append(
            {
                "prompt": prompt,
                "input_data": input_data,
                "response_schema": response_schema,
            }
        )
        return self.payload


def settings(api_key: str = "fake-key") -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        project_root=root,
        data_dir=root / "data",
        output_dir=root / "outputs",
        llm_provider="gemini",
        gemini_api_key=api_key,
        gemini_model="gemini-test",
        gemini_max_output_tokens=DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
        openai_api_key="",
        openai_model="",
        supabase_url="",
        supabase_key="",
        supabase_service_role_key="",
        supabase_storage_bucket=DEFAULT_STORAGE_BUCKET,
        storage_file_size_limit_bytes=DEFAULT_STORAGE_FILE_SIZE_LIMIT_BYTES,
        storage_allowed_mime_types=DEFAULT_STORAGE_ALLOWED_MIME_TYPES,
    )


def test_service_selects_prompt_and_schema() -> None:
    client = FakeClient(document_payload())
    service = StructuredExtractionService(client=client)

    result = service.extract(
        prompt_id="document_extraction", version="v1", content="contenido"
    )

    assert result.prompt_id == "document_extraction"
    assert result.prompt_version == "v1"
    assert result.contract_name == "DocumentExtraction"
    assert result.model_name == "fake-model"
    assert client.calls[0]["response_schema"]["title"] == "DocumentExtraction"
    assert "JSON Schema DocumentExtraction" in client.calls[0]["prompt"]
    assert client.calls[0]["input_data"].text == "contenido"


@pytest.mark.parametrize(
    ("prompt_id", "payload", "contract"),
    [
        ("document_extraction", document_payload(), "DocumentExtraction"),
        ("institutional_plan_extraction", institutional_payload(), "InstitutionalPlanExtraction"),
        ("policy_matrix_extraction", policy_payload(), "PolicyMatrixExtraction"),
        ("thematic_landscape", thematic_payload(), "ThematicLandscape"),
        ("regulatory_intelligence", regulatory_payload(), "RegulatoryIntelligence"),
        ("strategic_assessment", strategic_payload(), "StrategicAssessment"),
    ],
)
def test_service_accepts_valid_responses(prompt_id: str, payload: dict, contract: str) -> None:
    result = StructuredExtractionService(client=FakeClient(payload)).extract(
        prompt_id=prompt_id, version="v1", content="texto"
    )

    assert result.payload == payload
    assert result.contract_name == contract


def test_service_trims_transversal_payload_to_local_schema_limits() -> None:
    payload = thematic_payload()
    payload["corpus_summary"] = "x" * 2000
    payload["themes"] = payload["themes"] * 6
    payload["themes"][0]["definition"] = "y" * 1000
    payload["themes"][0]["subthemes"] = [f"subtema {index}" for index in range(10)]

    result = StructuredExtractionService(client=FakeClient(payload)).extract(
        prompt_id="thematic_landscape", version="v1", content="texto"
    )

    assert len(result.payload["corpus_summary"]) == 1200
    assert len(result.payload["themes"]) == 4
    assert len(result.payload["themes"][0]["definition"]) == 600
    assert len(result.payload["themes"][0]["subthemes"]) == 6


def test_service_rejects_invalid_response() -> None:
    service = StructuredExtractionService(client=FakeClient(document_payload("Muy alta")))

    with pytest.raises(Exception, match="DocumentExtraction.findings\\[0\\].confidence"):
        service.extract(prompt_id="document_extraction", version="v1", content="texto")


def test_service_trims_overlong_evidence_quotes_before_contract_validation() -> None:
    payload = document_payload()
    payload["evidence"][0]["quote"] = "Texto fuente." + ("x" * 600)

    result = StructuredExtractionService(client=FakeClient(payload)).extract(
        prompt_id="document_extraction", version="v1", content="texto"
    )

    assert len(result.payload["evidence"][0]["quote"]) == 500
    assert result.payload["evidence"][0]["quote"].startswith("Texto fuente.")


def test_service_rejects_invalid_transversal_response() -> None:
    service = StructuredExtractionService(client=FakeClient(thematic_payload("combine")))

    with pytest.raises(Exception, match="ThematicLandscape.themes\\[0\\].change_action"):
        service.extract(prompt_id="thematic_landscape", version="v1", content="texto")


def test_service_accepts_llm_input() -> None:
    client = FakeClient(document_payload())
    service = StructuredExtractionService(client=client)
    input_data = LLMInput(text="texto estructurado", metadata={"source": "excel"})

    service.extract(
        prompt_id="document_extraction", version="v1", input_data=input_data
    )

    assert client.calls[0]["input_data"] == input_data


def test_pdf_input_keeps_original_bytes_and_mime_type() -> None:
    file_bytes = b"%PDF-original"
    input_data = build_pdf_input(
        file_name="doc.pdf",
        file_bytes=file_bytes,
        metadata={"document_id": "doc-1"},
    )

    assert input_data.file_bytes is file_bytes
    assert input_data.mime_type == "application/pdf"
    assert input_data.file_name == "doc.pdf"
    assert input_data.metadata == {"document_id": "doc-1"}
    assert "PDF original" in input_data.text


def test_pdf_input_adds_institutional_smoke_limits() -> None:
    input_data = build_pdf_input(
        file_name="pmge.pdf",
        file_bytes=b"%PDF",
        metadata={"source_type": "institutional_plan", "smoke": "true"},
    )

    assert "MODO SMOKE TECNICO" in input_data.text
    assert "maximo 2 proyectos PMGE" in input_data.text
    assert "8 evidencias" in input_data.text


def test_pdf_input_adds_surveillance_smoke_limits() -> None:
    input_data = build_pdf_input(
        file_name="reporte.pdf",
        file_bytes=b"%PDF",
        metadata={"source_type": "surveillance", "smoke": "true"},
    )

    assert "maximo 3 hallazgos" in input_data.text
    assert "5 evidencias" in input_data.text
    assert "maximo 3 items por campo de lista" in input_data.text


def test_excel_input_does_not_send_binary_and_preserves_sheets_rows() -> None:
    chunks = [
        DocumentChunk(
            id="2",
            document_id="doc-1",
            content="second",
            page_number=None,
            section_title=None,
            sheet_name="Hoja B",
            row_reference="5",
            content_hash="h2",
            position=2,
        ),
        DocumentChunk(
            id="1",
            document_id="doc-1",
            content="first",
            page_number=None,
            section_title=None,
            sheet_name="Hoja A",
            row_reference="2",
            content_hash="h1",
            position=1,
        ),
    ]

    input_data = build_excel_input(
        file_name="book.xlsx",
        chunks=chunks,
        metadata={"document_id": "doc-1"},
    )

    assert input_data.file_bytes is None
    assert input_data.file_name == "book.xlsx"
    assert input_data.text.index("Hoja A") < input_data.text.index("Hoja B")
    assert "ROW_REFERENCE: 2" in input_data.text
    assert "ROW_REFERENCE: 5" in input_data.text
    assert "first" in input_data.text
    assert "second" in input_data.text


def test_excel_input_adds_policy_smoke_limits() -> None:
    input_data = build_excel_input(
        file_name="matriz.xlsx",
        chunks=[],
        metadata={"source_type": "policy_matrix", "smoke": "1"},
    )

    assert "MODO SMOKE TECNICO" in input_data.text
    assert "maximo 3 politicas" in input_data.text
    assert "copia literal corta" in input_data.text
    assert "ROW_REFERENCE" in input_data.text


def test_missing_prompt_fails() -> None:
    with pytest.raises(KeyError):
        StructuredExtractionService(client=FakeClient()).extract(
            prompt_id="no_existe", version="v1", content="texto"
        )


def test_gemini_missing_api_key_is_rejected() -> None:
    client = GeminiStructuredClient(settings=settings(api_key=""))

    with pytest.raises(MissingConfigurationError):
        client.generate_json(
            prompt="p", input_data=LLMInput(text="c"), response_schema={"type": "object"}
        )


def test_gemini_empty_response_is_rejected() -> None:
    fake_google = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text="")
        )
    )
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(EmptyLLMResponseError):
        client.generate_json(
            prompt="p", input_data=LLMInput(text="c"), response_schema={"type": "object"}
        )


def test_gemini_malformed_json_is_rejected() -> None:
    fake_google = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text="{mal")
        )
    )
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(InvalidLLMJSONError):
        client.generate_json(
            prompt="p", input_data=LLMInput(text="c"), response_schema={"type": "object"}
        )


def test_gemini_retries_once_with_compact_instruction_after_invalid_json() -> None:
    calls: list[dict] = []

    def generate_content(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return SimpleNamespace(text='{"ok": "truncado')
        return SimpleNamespace(text='{"ok": true}')

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    result = client.generate_json(
        prompt="Prompt",
        input_data=LLMInput(text="contenido"),
        response_schema={"type": "object"},
    )

    assert result == {"ok": True}
    assert len(calls) == 2
    assert "REINTENTO POR JSON INVALIDO" in calls[1]["contents"][0].text


def test_gemini_provider_error_is_wrapped() -> None:
    def fail(**kwargs):
        raise RuntimeError("boom")

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(LLMProviderError, match="boom"):
        client.generate_json(
            prompt="p", input_data=LLMInput(text="c"), response_schema={"type": "object"}
        )


def test_gemini_client_is_created_lazily() -> None:
    calls: list[str] = []

    def factory(**kwargs):
        calls.append(kwargs["api_key"])
        return SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **call: SimpleNamespace(text='{"ok": true}')
            )
        )

    client = GeminiStructuredClient(settings=settings(), client_factory=factory)
    assert calls == []

    result = client.generate_json(
        prompt="p", input_data=LLMInput(text="c"), response_schema={"type": "object"}
    )

    assert result == {"ok": True}
    assert calls == ["fake-key"]


def test_gemini_receives_text_metadata_and_pdf_part() -> None:
    captured: dict = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text='{"ok": true}')

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )
    input_data = build_pdf_input(
        file_name="doc.pdf",
        file_bytes=b"%PDF bytes",
        metadata={"document_id": "doc-1"},
    )

    result = client.generate_json(
        prompt="Prompt",
        input_data=input_data,
        response_schema={"type": "object"},
    )

    assert result == {"ok": True}
    parts = captured["contents"]
    assert len(parts) == 2
    assert parts[0].text is not None
    assert "document_id" in parts[0].text
    assert "doc.pdf" in parts[0].text
    assert parts[1].inline_data.mime_type == "application/pdf"
    assert parts[1].inline_data.data == b"%PDF bytes"
    assert captured["config"].response_json_schema == {"type": "object"}
    assert captured["config"].response_schema is None
    assert captured["config"].max_output_tokens == DEFAULT_GEMINI_MAX_OUTPUT_TOKENS


def test_gemini_strips_provider_unsafe_schema_constraints() -> None:
    captured: dict = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text='{"ok": true}')

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    client.generate_json(
        prompt="Prompt",
        input_data=LLMInput(text="contenido"),
        response_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "description": "schema completo",
            "properties": {
                "description": {"type": "string", "maxLength": 10},
                "items": {
                    "type": "array",
                    "maxItems": 2,
                    "items": {"type": "string", "maxLength": 5},
                }
            },
        },
    )

    schema = captured["config"].response_json_schema
    assert "$schema" not in schema
    assert "description" not in schema
    assert "description" in schema["properties"]
    assert "maxItems" not in str(schema)
    assert "maxLength" not in str(schema)


def test_gemini_excel_input_sends_only_text_and_metadata() -> None:
    captured: dict = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text='{"ok": true}')

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )
    input_data = LLMInput(
        text="=== SHEET: Hoja ===\nROW_REFERENCE: 2",
        metadata={"kind": "excel"},
        file_name="book.xlsx",
    )

    client.generate_json(
        prompt="Prompt",
        input_data=input_data,
        response_schema={"type": "object"},
    )

    parts = captured["contents"]
    assert len(parts) == 1
    assert "ROW_REFERENCE: 2" in parts[0].text
    assert "kind" in parts[0].text


def test_normalize_provider_payload_drops_empty_optional_field_violating_min_length() -> None:
    """Regresion: Gemini a veces manda un campo opcional como '' en vez de omitirlo.

    theme_id no es requerido en RegulatoryIntelligenceItem pero exige minLength=1
    cuando esta presente. Si se deja la cadena vacia, la validacion del contrato
    falla y tumba todo el analisis transversal aunque el resto del payload sea
    valido. Debe descartarse el campo, no el registro completo.
    """
    from app.llm.service import _normalize_provider_payload

    schema = {
        "type": "object",
        "required": ["temporary_id"],
        "properties": {
            "temporary_id": {"type": "string", "minLength": 1},
            "theme_id": {"type": "string", "minLength": 1},
        },
    }
    payload = {"temporary_id": "item-1", "theme_id": ""}

    normalized = _normalize_provider_payload(payload, schema)

    assert normalized == {"temporary_id": "item-1"}


def test_normalize_provider_payload_keeps_required_empty_field_so_validation_still_fails() -> None:
    """Un campo requerido vacio si debe seguir fallando: es una senal real de error."""
    from app.llm.service import _normalize_provider_payload

    schema = {
        "type": "object",
        "required": ["temporary_id"],
        "properties": {"temporary_id": {"type": "string", "minLength": 1}},
    }
    payload = {"temporary_id": ""}

    normalized = _normalize_provider_payload(payload, schema)

    assert normalized == {"temporary_id": ""}
