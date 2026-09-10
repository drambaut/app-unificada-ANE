"""Normalizacion y persistencia abstracta de resultados."""

from app.results.in_memory_repository import InMemoryResultRepository
from app.results.models import PersistenceBundle, ResultRecord
from app.results.normalizer import ResultNormalizer
from app.results.service import ResultPersistenceService

__all__ = [
    "InMemoryResultRepository",
    "PersistenceBundle",
    "ResultNormalizer",
    "ResultPersistenceService",
    "ResultRecord",
]
