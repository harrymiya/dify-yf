"""add KB knowledge-graph tables (requirement 1, tasks C4/C5)

Revision ID: e9f3c7b1d5a4
Revises: a7f2b91c3e01
Create Date: 2026-08-18 14:00:00.000000

Implements customization requirement 1 (knowledge graph sub-module). Per the
implementation plan's §8 decision, the graph is first prototyped with
relational tables before any graph database is adopted.

Adds two tenant/dataset-scoped tables:

- ``graph_entities``: graph nodes (an entity name, type and optional description)
  scoped to a tenant and (optionally) a dataset / document so the same
  four-layer KB permission whitelist (B5 / C5) can isolate access.
- ``graph_relations``: typed directed edges between two graph entities.

Both carry the ``tenant_id`` owner chain used for permission isolation (C5).

"""

import sqlalchemy as sa
from alembic import op

import models as models

# revision identifiers, used by Alembic.
revision = "e9f3c7b1d5a4"
down_revision = "a7f2b91c3e01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "graph_entities",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("dataset_id", models.types.StringUUID(), nullable=True),
        sa.Column("document_id", models.types.StringUUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="graph_entity_pkey"),
    )
    op.create_index("idx_graph_entities_tenant_dataset", "graph_entities", ["tenant_id", "dataset_id"], unique=False)
    op.create_index("idx_graph_entities_name", "graph_entities", ["tenant_id", "name"], unique=False)

    op.create_table(
        "graph_relations",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("source_entity_id", models.types.StringUUID(), nullable=False),
        sa.Column("target_entity_id", models.types.StringUUID(), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="graph_relation_pkey"),
    )
    op.create_index("idx_graph_relations_tenant", "graph_relations", ["tenant_id"], unique=False)
    op.create_index("idx_graph_relations_source", "graph_relations", ["tenant_id", "source_entity_id"], unique=False)


def downgrade():
    op.drop_index("idx_graph_relations_source", table_name="graph_relations")
    op.drop_index("idx_graph_relations_tenant", table_name="graph_relations")
    op.drop_table("graph_relations")

    op.drop_index("idx_graph_entities_name", table_name="graph_entities")
    op.drop_index("idx_graph_entities_tenant_dataset", table_name="graph_entities")
    op.drop_table("graph_entities")
