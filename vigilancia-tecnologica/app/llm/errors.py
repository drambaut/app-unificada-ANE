"""Errores propios de la capa LLM modular."""


class LLMServiceError(Exception):
    """Error base de la capa LLM."""


class MissingConfigurationError(LLMServiceError):
    """Falta configuracion requerida para ejecutar un cliente."""


class EmptyLLMResponseError(LLMServiceError):
    """El proveedor devolvio una respuesta vacia."""


class InvalidLLMJSONError(LLMServiceError):
    """El proveedor devolvio JSON invalido o no objeto."""


class LLMProviderError(LLMServiceError):
    """El proveedor fallo durante la solicitud."""


class InvalidContractError(LLMServiceError):
    """El prompt no tiene contrato soportado por el servicio."""
