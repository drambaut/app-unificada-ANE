"""Registro declarativo de prompts versionados."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str
    path: Path
    contract: str
    status: str
    description: str


PROMPT_REGISTRY: tuple[PromptSpec, ...] = (
    PromptSpec(
        prompt_id="legacy_document_extraction",
        version="legacy",
        path=Path("prompts/legacy/extraction_prompt.txt"),
        contract="LegacyStructuredDocument",
        status="legacy",
        description="Prompt original del MVP basado en structured_documents.csv.",
    ),
    PromptSpec(
        prompt_id="document_extraction",
        version="v1",
        path=Path("prompts/v1/document_extraction.txt"),
        contract="DocumentExtraction",
        status="active",
        description="Extraccion de ficha documental, hallazgos y evidencia para vigilancia.",
    ),
    PromptSpec(
        prompt_id="institutional_plan_extraction",
        version="v1",
        path=Path("prompts/v1/institutional_plan_extraction.txt"),
        contract="InstitutionalPlanExtraction",
        status="active",
        description="Extraccion separada de PMGE y Agenda Regulatoria.",
    ),
    PromptSpec(
        prompt_id="policy_matrix_extraction",
        version="v1",
        path=Path("prompts/v1/policy_matrix_extraction.txt"),
        contract="PolicyMatrixExtraction",
        status="active",
        description="Extraccion de politicas, actividades, compromisos y evidencia.",
    ),
    PromptSpec(
        prompt_id="thematic_landscape",
        version="v1",
        path=Path("prompts/v1/thematic_landscape.txt"),
        contract="ThematicLandscape",
        status="active",
        description="Analisis transversal de paisaje tematico del corpus.",
    ),
    PromptSpec(
        prompt_id="regulatory_intelligence",
        version="v1",
        path=Path("prompts/v1/regulatory_intelligence.txt"),
        contract="RegulatoryIntelligence",
        status="active",
        description="Comparacion regulatoria entre panorama tematico, corpus y Agenda.",
    ),
    PromptSpec(
        prompt_id="strategic_assessment",
        version="v1",
        path=Path("prompts/v1/strategic_assessment.txt"),
        contract="StrategicAssessment",
        status="active",
        description="Evaluacion separada de importancia, oportunidad y alineacion.",
    ),
)


def get_prompt_spec(prompt_id: str, version: str) -> PromptSpec:
    """Devuelve la especificacion registrada para un prompt y version."""
    for spec in PROMPT_REGISTRY:
        if spec.prompt_id == prompt_id and spec.version == version:
            return spec
    available = ", ".join(
        f"{spec.prompt_id}@{spec.version}" for spec in PROMPT_REGISTRY
    )
    raise KeyError(
        f"No existe prompt registrado para prompt_id='{prompt_id}' y version='{version}'. "
        f"Disponibles: {available}"
    )
