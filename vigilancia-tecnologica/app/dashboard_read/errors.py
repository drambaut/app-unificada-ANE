"""Errores de lectura del dashboard publicado."""


class DashboardReadError(Exception):
    """Error base del modulo de lectura para dashboard."""


class NoPublishedAnalysisRunError(DashboardReadError):
    """No existe una ejecucion publicada vigente."""


class IncompletePublishedRunError(DashboardReadError):
    """La ejecucion publicada no tiene todos los resultados requeridos."""


class InconsistentSnapshotError(DashboardReadError):
    """El snapshot publicado no coincide con los datos disponibles."""


class DashboardMappingError(DashboardReadError):
    """No fue posible mapear datos publicados a una vista estable."""

