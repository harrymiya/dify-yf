"""add audit_logs table (requirement 5)

Revision ID: a7f2b91c3e01
Revises: cbed6f41a0d2
Create Date: 2026-08-18 12:00:00.000000

Implements customization requirement 5 (5-class audit logs: Q&A / retrieval /
document download / permission change / system). Adds a single unified
``audit_logs`` table that references request/trace/identity context.

"""

import sqlalchemy as sa
from alembic import op

import models as models

# revision identifiers, used by Alembic.
revision = "a7f2b91c3e01"
down_revision = "cbed6f41a0d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "kb_audit_logs",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("user_id", models.types.StringUUID(), nullable=True),
        sa.Column("user_type", sa.String(length=32), nullable=True),
        sa.Column("log_type", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=True),
        sa.Column("resource_id", models.types.StringUUID(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=16), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="kb_audit_log_pkey"),
    )
    op.create_index("idx_kb_audit_logs_tenant_created", "kb_audit_logs", ["tenant_id", "created_at"], unique=False)
    op.create_index("idx_kb_audit_logs_tenant_type", "kb_audit_logs", ["tenant_id", "log_type"], unique=False)


def downgrade():
    op.drop_index("idx_kb_audit_logs_tenant_type", table_name="kb_audit_logs")
    op.drop_index("idx_kb_audit_logs_tenant_created", table_name="kb_audit_logs")
    op.drop_table("kb_audit_logs")
