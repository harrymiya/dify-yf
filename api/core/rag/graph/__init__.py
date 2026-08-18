"""Knowledge-graph sub-module (requirement 1, tasks C4/C5).

Provides entity extraction (:mod:`entity_extractor`), build/retrieval
(:mod:`graph_service`), prompt templates (:mod:`prompts`) and result models
(:mod:`entities`). Permission isolation (C5) reuses the B5 four-layer whitelist
inside :meth:`GraphService.retrieve`.
"""

from core.rag.graph.entities import (
    GraphBuildResult,
    GraphEntityRecord,
    GraphRelationRecord,
    GraphRetrievalResult,
)
from core.rag.graph.entity_extractor import Extractor, GraphEntityExtractor
from core.rag.graph.graph_service import GraphService

__all__ = [
    "Extractor",
    "GraphBuildResult",
    "GraphEntityExtractor",
    "GraphEntityRecord",
    "GraphRelationRecord",
    "GraphRetrievalResult",
    "GraphService",
]
