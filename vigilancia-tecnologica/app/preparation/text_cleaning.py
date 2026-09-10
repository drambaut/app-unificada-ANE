"""Limpieza tecnica de texto antes de persistir chunks."""

from __future__ import annotations


def clean_chunk_text(value: str) -> str:
    """Remueve caracteres que PostgreSQL no acepta en columnas text."""
    return "".join(
        character
        for character in value
        if character == "\n" or character == "\t" or ord(character) >= 32
    )
