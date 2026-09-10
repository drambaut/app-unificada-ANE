"""Errores de preparacion tecnica de documentos."""


class DocumentPreparationError(Exception):
    """Error base de preparacion documental."""


class UnsupportedDocumentFormatError(DocumentPreparationError):
    """La extension del documento no tiene preparador disponible."""


class PreparationJobNotFoundError(DocumentPreparationError):
    """El documento no tiene job DOCUMENT_PREPARATION."""


class OcrRequiredError(DocumentPreparationError):
    """El PDF no contiene texto suficiente y puede requerir OCR."""
