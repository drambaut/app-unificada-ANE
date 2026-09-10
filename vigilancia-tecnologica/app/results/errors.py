"""Errores de normalizacion y persistencia de resultados."""


class ResultPersistenceError(Exception):
    """Error base de resultados."""


class ResultNormalizationError(ResultPersistenceError):
    """El payload validado no puede normalizarse con seguridad."""


class DuplicateResultError(ResultPersistenceError):
    """Ya existe un resultado equivalente o persistido."""


class ResultPersistenceWorkflowError(ResultPersistenceError):
    """Fallo controlado en el workflow de persistencia."""
