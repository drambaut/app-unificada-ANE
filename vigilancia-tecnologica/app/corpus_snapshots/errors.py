"""Errores del modulo de instantaneas del corpus."""


class CorpusSnapshotError(Exception):
    """Error base del modulo."""


class CorpusSnapshotNotFoundError(CorpusSnapshotError):
    """La instantanea solicitada no existe."""


class DuplicateCorpusSnapshotError(CorpusSnapshotError):
    """Ya existe una instantanea con el mismo ID."""


class InvalidCorpusSnapshotError(CorpusSnapshotError):
    """La instantanea no cumple las reglas del dominio."""


class InvalidSnapshotReferenceError(CorpusSnapshotError):
    """Una referencia incluida en la instantanea no es valida."""

