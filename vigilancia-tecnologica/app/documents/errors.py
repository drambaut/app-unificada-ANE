"""Errores del dominio documental."""


class DocumentDomainError(Exception):
    """Error base del dominio documental."""


class DuplicateDocumentError(DocumentDomainError):
    """El documento ya existe para el mismo hash."""


class DocumentNotFoundError(DocumentDomainError):
    """No existe el documento solicitado."""


class ProcessingJobNotFoundError(DocumentDomainError):
    """No existe el job solicitado."""


class InvalidDocumentStatusTransition(DocumentDomainError):
    """La transicion de estado documental no esta permitida."""


class InvalidProcessingJobSequence(DocumentDomainError):
    """El job solicitado no respeta la secuencia del flujo documental."""


class DuplicateProcessingJobError(DocumentDomainError):
    """Ya existe un job equivalente para el documento."""
