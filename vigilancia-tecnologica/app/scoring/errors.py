"""Errores de scoring estrategico."""


class ScoringError(Exception):
    """Error base del modulo de scoring."""


class InvalidScoringDimensionsError(ScoringError):
    """Las dimensiones requeridas para calcular el score no son validas."""

