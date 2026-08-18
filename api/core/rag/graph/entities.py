"""Knowledge-graph result dataclasses (requirement 1, tasks C4/C5).

Graph retrieval returns normalized records (entities + traversed relations)
that the console controller serializes for the frontend graph page and the
multi-assistant retrieval pipeline can also reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GraphEntityRecord:
    """A graph entity (node) surfaced by graph retrieval."""

    id: str
    name: str
    entity_type: str | None = None
    description: str | None = None
    dataset_id: str | None = None
    document_id: str | None = None
    #: relevance / depth-decayed score assigned during retrieval.
    score: float = 0.0

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "dataset_id": self.dataset_id,
            "document_id": self.document_id,
            "score": self.score,
        }


@dataclass(slots=True)
class GraphRelationRecord:
    """A typed directed edge between two graph entities."""

    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    detail: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relation_type": self.relation_type,
            "detail": self.detail,
        }


@dataclass(slots=True)
class GraphRetrievalResult:
    """The full result of a graph retrieval: matched entities plus traversal."""

    query: str
    records: list[GraphEntityRecord] = field(default_factory=list)
    relations: list[GraphRelationRecord] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "records": [r.to_payload() for r in self.records],
            "relations": [r.to_payload() for r in self.relations],
        }


@dataclass(slots=True)
class GraphBuildResult:
    """Summary counters returned by a graph build run."""

    entities_created: int = 0
    entities_matched: int = 0
    relations_created: int = 0
    segments_processed: int = 0
    segments_skipped: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "entities_created": self.entities_created,
            "entities_matched": self.entities_matched,
            "relations_created": self.relations_created,
            "segments_processed": self.segments_processed,
            "segments_skipped": self.segments_skipped,
        }
