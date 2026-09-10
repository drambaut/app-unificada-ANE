"""Constructores de entradas LLM para documentos preparados."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.documents.models import DocumentChunk
from app.llm.base import LLMInput


def build_pdf_input(
    *,
    file_name: str,
    file_bytes: bytes,
    metadata: Mapping[str, str] | None = None,
) -> LLMInput:
    """Construye entrada PDF conservando los bytes originales."""
    normalized_metadata = dict(metadata or {})
    text = "Analiza el PDF original adjunto usando estos metadatos como contexto."
    if _is_smoke_mode(normalized_metadata):
        text = "\n\n".join((text, _smoke_mode_instruction(normalized_metadata)))
    return LLMInput(
        text=text,
        file_bytes=file_bytes,
        mime_type="application/pdf",
        file_name=file_name,
        metadata=normalized_metadata,
    )


def build_excel_input(
    *,
    file_name: str,
    chunks: Iterable[DocumentChunk],
    metadata: Mapping[str, str] | None = None,
) -> LLMInput:
    """Construye entrada textual estructurada desde chunks Excel."""
    normalized_metadata = dict(metadata or {})
    ordered_chunks = sorted(chunks, key=lambda chunk: chunk.position)
    lines = [
        f"ARCHIVO: {file_name}",
        "CONTENIDO ESTRUCTURADO POR HOJAS Y FILAS",
    ]
    if _is_smoke_mode(normalized_metadata):
        lines.append("")
        lines.append(_smoke_mode_instruction(normalized_metadata))
    current_sheet: str | None = None
    for chunk in ordered_chunks:
        sheet_name = chunk.sheet_name or ""
        if sheet_name != current_sheet:
            lines.append("")
            lines.append(f"=== SHEET: {sheet_name} ===")
            current_sheet = sheet_name
        lines.extend(
            [
                f"ROW_REFERENCE: {chunk.row_reference or ''}",
                "CONTENT:",
                chunk.content,
                "---",
            ]
        )

    return LLMInput(
        text="\n".join(lines).strip(),
        file_bytes=None,
        mime_type=None,
        file_name=file_name,
        metadata=normalized_metadata,
    )


def _is_smoke_mode(metadata: Mapping[str, str]) -> bool:
    return str(metadata.get("smoke", "")).strip().casefold() in {"1", "true", "yes", "si"}


def _smoke_mode_instruction(metadata: Mapping[str, str]) -> str:
    source_type = str(metadata.get("source_type", "")).strip()
    if source_type == "institutional_plan":
        return (
            "MODO SMOKE TECNICO: esta ejecucion valida el flujo de arquitectura, "
            "no busca una extraccion exhaustiva. Devuelve una muestra pequena y "
            "valida: maximo 2 proyectos PMGE, 2 objetivos, 3 actividades, "
            "2 iniciativas de Agenda Regulatoria, 3 entregables y 8 evidencias. "
            "Prioriza elementos claramente explicitos, con citas cortas y "
            "verificables. Usa listas vacias para lo no incluido en la muestra."
        )
    if source_type == "policy_matrix":
        return (
            "MODO SMOKE TECNICO: devuelve una muestra pequena y valida, no una "
            "extraccion exhaustiva. Usa maximo 3 politicas, 5 actividades, "
            "5 compromisos y 8 evidencias. Si el insumo es Excel, cada quote "
            "debe ser una copia literal corta tomada del bloque CONTENT de la "
            "fila usada, y sheet_name/row_reference deben coincidir exactamente "
            "con los marcadores SHEET y ROW_REFERENCE."
        )
    return (
        "MODO SMOKE TECNICO: devuelve una muestra pequena y valida, no una "
        "extraccion exhaustiva. Usa maximo 3 hallazgos y 5 evidencias. Evita "
        "listas largas: maximo 3 items por campo de lista. Cada title, summary, "
        "description y quote debe ser corto. Si el insumo es Excel, cada quote "
        "debe ser una copia literal corta tomada del bloque CONTENT de la fila "
        "usada, y sheet_name/row_reference deben coincidir exactamente con los "
        "marcadores SHEET y ROW_REFERENCE."
    )
