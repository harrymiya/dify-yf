"""Knowledge graph models - requirement 1 (task C4/C5).

A lightweight relational-table knowledge graph (per the plan's §8 suggestion to
prototype with relational tables before adopting a graph DB). Entities and typed
relations are stored tenant/dataset-scoped so they can be isolated by the same
four-layer KB permission whitelist (B5) used elsewhere.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class GraphEntity(TypeBase):
    """A knowledge graph entity (node), scoped to a tenant and (optionally) a dataset."""

    __tablename__ = "graph_entities"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="graph_entity_pkey"),
        Index("idx_graph_entities_tenant_dataset", "tenant_id", "dataset_id"),
        Index("idx_graph_entities_name", "tenant_id", "name"),
    )

    # NOTE: required (non-default) fields must precede optional (defaulted) fields
    # for the SQLAlchemy ``MappedAsDataclass`` constructor.
    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    document_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    # e.g. product / tech / org / person
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )

    def __repr__(self) -> str:
        return f"<GraphEntity id={self.id!r} tenant={self.tenant_id!r} name={self.name!r}>"


class GraphRelation(TypeBase):
    """A typed directed relation between two graph entities (edge)."""

    __tablename__ = "graph_relations"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="graph_relation_pkey"),
        Index("idx_graph_relations_tenant", "tenant_id"),
        Index("idx_graph_relations_source", "tenant_id", "source_entity_id"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "depends_on" / "part_of"
    detail: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )

    def __repr__(self) -> str:
        return (
            f"<GraphRelation id={self.id!r} {self.source_entity_id!r} --{self.relation_type}--> "
            f"{self.target_entity_id!r}>"
        )
