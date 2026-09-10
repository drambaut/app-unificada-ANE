"""Errores del modulo de ejecuciones de analisis transversal."""


class AnalysisRunError(Exception):
    """Error base del modulo."""


class AnalysisRunNotFoundError(AnalysisRunError):
    """La ejecucion solicitada no existe."""


class AnalysisStageNotFoundError(AnalysisRunError):
    """La etapa solicitada no existe."""


class InvalidAnalysisTransitionError(AnalysisRunError):
    """La transicion de estado solicitada no esta permitida."""


class ConcurrentAnalysisRunError(AnalysisRunError):
    """Ya existe una ejecucion activa para la misma instantanea."""


class IncompleteAnalysisPublicationError(AnalysisRunError):
    """La ejecucion no esta completa y no puede publicarse."""


class InvalidAnalysisRetryError(AnalysisRunError):
    """La etapa no puede prepararse para reintento."""

