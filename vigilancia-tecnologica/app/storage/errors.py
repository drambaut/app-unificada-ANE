"""Errores de almacenamiento de documentos fuente."""


class StorageError(Exception):
    """Error base para adaptadores de Storage."""


class StorageConfigurationError(StorageError):
    """Configuracion incompleta para conectar con Storage."""


class StorageValidationError(StorageError):
    """Archivo invalido para las reglas de Storage configuradas."""
