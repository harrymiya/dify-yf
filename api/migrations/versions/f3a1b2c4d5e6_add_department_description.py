"""add description column to departments

Revision ID: f3a1b2c4d5e6
Revises: e9f3c7b1d5a4
Create Date: 2026-08-20 00:00:00.000000

Adds an optional description field to the tenant-scoped department (org tree)
so the department detail panel can display a description instead of the raw id.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3a1b2c4d5e6"
down_revision = "e9f3c7b1d5a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("departments", sa.Column("description", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("departments", "description")
