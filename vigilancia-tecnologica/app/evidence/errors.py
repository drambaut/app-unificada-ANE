"""Errores de validacion de evidencia."""


class EvidenceValidationError(Exception):
    """Error base de validacion de evidencia."""


class EvidenceValidationWorkflowError(EvidenceValidationError):
    """Fallo controlado en el workflow de validacion de evidencia."""
