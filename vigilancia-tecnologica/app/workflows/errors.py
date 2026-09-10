"""Errores de workflows de aplicacion."""


class WorkflowError(Exception):
    """Fallo controlado en una etapa del workflow."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        super().__init__(f"{stage}: {message}")
