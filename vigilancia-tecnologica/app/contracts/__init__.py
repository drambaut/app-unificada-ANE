"""Contratos JSON Schema para extracciones estructuradas."""

from app.contracts.document_extraction import DOCUMENT_EXTRACTION_SCHEMA
from app.contracts.institutional_plan import INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA
from app.contracts.policy_matrix import POLICY_MATRIX_EXTRACTION_SCHEMA
from app.contracts.regulatory_intelligence import REGULATORY_INTELLIGENCE_SCHEMA
from app.contracts.strategic_assessment import STRATEGIC_ASSESSMENT_SCHEMA
from app.contracts.thematic_landscape import THEMATIC_LANDSCAPE_SCHEMA

__all__ = [
    "DOCUMENT_EXTRACTION_SCHEMA",
    "INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA",
    "POLICY_MATRIX_EXTRACTION_SCHEMA",
    "REGULATORY_INTELLIGENCE_SCHEMA",
    "STRATEGIC_ASSESSMENT_SCHEMA",
    "THEMATIC_LANDSCAPE_SCHEMA",
]
