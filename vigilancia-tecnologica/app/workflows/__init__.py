"""Workflows de la nueva arquitectura modular."""

from app.workflows.document_analysis import (
    DocumentAnalysisWorkflow,
    DocumentAnalysisWorkflowResult,
)
from app.workflows.document_processing import (
    DocumentProcessingWorkflow,
    DocumentProcessingWorkflowError,
    DocumentProcessingWorkflowResult,
)
from app.workflows.errors import WorkflowError

__all__ = [
    "DocumentAnalysisWorkflow",
    "DocumentAnalysisWorkflowResult",
    "DocumentProcessingWorkflow",
    "DocumentProcessingWorkflowError",
    "DocumentProcessingWorkflowResult",
    "WorkflowError",
]
