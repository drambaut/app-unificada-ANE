"""Componentes comunes para contratos JSON Schema."""

CONFIDENCE_VALUES = ["Alta", "Media", "Baja"]
EXTRACTION_BASIS_VALUES = ["explicit", "inferred", "mixed"]
EVIDENCE_TYPE_VALUES = [
    "cita_textual",
    "tabla",
    "encabezado",
    "lista",
    "metadato",
    "grafica",
    "nota_pie",
]

TEMPORARY_ID = {
    "type": "string",
    "minLength": 1,
    "description": "Identificador temporal dentro de la respuesta LLM. El backend generara IDs persistentes.",
}

CONFIDENCE = {"type": "string", "enum": CONFIDENCE_VALUES}
EXTRACTION_BASIS = {"type": "string", "enum": EXTRACTION_BASIS_VALUES}
EVIDENCE_IDS = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "description": "temporary_id de evidencias que soportan la entidad.",
}

OPEN_TEXT_LIST = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Lista abierta de textos; no usar taxonomias cerradas en esta etapa.",
}

EVIDENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "quote",
        "evidence_type",
        "page_number",
        "sheet_name",
        "row_reference",
        "section_title",
        "confidence",
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "quote": {
            "type": "string",
            "maxLength": 500,
            "description": "Fragmento textual breve que soporta la extraccion.",
        },
        "evidence_type": {"type": "string", "enum": EVIDENCE_TYPE_VALUES},
        "page_number": {"type": ["integer", "null"], "minimum": 1},
        "sheet_name": {"type": ["string", "null"]},
        "row_reference": {"type": ["string", "null"]},
        "section_title": {"type": ["string", "null"]},
        "confidence": CONFIDENCE,
    },
}


def array_of(schema: dict, min_items: int = 0, max_items: int | None = None) -> dict:
    """Declara una lista JSON Schema reutilizable."""
    result = {"type": "array", "items": schema, "minItems": min_items}
    if max_items is not None:
        result["maxItems"] = max_items
    return result
