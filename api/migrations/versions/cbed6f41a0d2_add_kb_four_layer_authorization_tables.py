"""add kb four-layer authorization tables (departments / roles / grants)

Revision ID: cbed6f41a0d2
Revises: 56124e050600
Create Date: 2026-08-18 00:00:00.000000

Implements customization requirement 3 (knowledge query permission, four-layer
authorization: department - role - knowledge scope/document - operation).

Adds the tenant-scoped org tree, custom roles and the core grant table:

- ``departments``: self-referencing org tree (tenant scoped).
- ``department_members``: account membership in a department.
- ``roles``: custom (non built-in) roles used as authorization subjects.
- ``user_roles``: binds an account to a custom role within a tenant.
- ``kb_permission_grants``: the unified subject x resource x action grant table
  (account / department / role  x  dataset / document  x  operation), default deny.

The existing ``dataset_permissions`` table is left untouched for backward
compatibility (account-level model).

"""

import sqlalchemy as sa
from alembic import op

import models as models

# revision identifiers, used by Alembic.
revision = "cbed6f41a0d2"
down_revision = "56124e050600"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "departments",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("parent_id", models.types.StringUUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="department_pkey"),
    )
    op.create_index("idx_departments_tenant_id", "departments", ["tenant_id"], unique=False)
    op.create_index("idx_departments_parent_id", "departments", ["parent_id"], unique=False)

    op.create_table(
        "department_members",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("department_id", models.types.StringUUID(), nullable=False),
        sa.Column("account_id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="department_member_pkey"),
    )
    op.create_index("idx_department_members_department_id", "department_members", ["department_id"], unique=False)
    op.create_index("idx_department_members_account_id", "department_members", ["account_id"], unique=False)
    op.create_index("idx_department_members_tenant_id", "department_members", ["tenant_id"], unique=False)

    op.create_table(
        "kb_roles",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("built_in", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="kb_role_pkey"),
    )
    op.create_index("idx_kb_roles_tenant_id", "kb_roles", ["tenant_id"], unique=False)

    op.create_table(
        "kb_user_roles",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("user_id", models.types.StringUUID(), nullable=False),
        sa.Column("role_id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="kb_user_role_pkey"),
    )
    op.create_index("idx_kb_user_roles_user_id", "kb_user_roles", ["user_id"], unique=False)
    op.create_index("idx_kb_user_roles_role_id", "kb_user_roles", ["role_id"], unique=False)
    op.create_index("idx_kb_user_roles_tenant_id", "kb_user_roles", ["tenant_id"], unique=False)

    op.create_table(
        "kb_permission_grants",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", models.types.StringUUID(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", models.types.StringUUID(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("created_by", models.types.StringUUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="kb_permission_grant_pkey"),
    )
    op.create_index(
        "idx_kb_grants_tenant_resource", "kb_permission_grants", ["tenant_id", "resource_type", "resource_id"], unique=False
    )
    op.create_index("idx_kb_grants_subject", "kb_permission_grants", ["subject_type", "subject_id"], unique=False)


def downgrade():
    op.drop_index("idx_kb_grants_subject", table_name="kb_permission_grants")
    op.drop_index("idx_kb_grants_tenant_resource", table_name="kb_permission_grants")
    op.drop_table("kb_permission_grants")

    op.drop_index("idx_kb_user_roles_tenant_id", table_name="kb_user_roles")
    op.drop_index("idx_kb_user_roles_role_id", table_name="kb_user_roles")
    op.drop_index("idx_kb_user_roles_user_id", table_name="kb_user_roles")
    op.drop_table("kb_user_roles")

    op.drop_index("idx_kb_roles_tenant_id", table_name="kb_roles")
    op.drop_table("kb_roles")

    op.drop_index("idx_department_members_tenant_id", table_name="department_members")
    op.drop_index("idx_department_members_account_id", table_name="department_members")
    op.drop_index("idx_department_members_department_id", table_name="department_members")
    op.drop_table("department_members")

    op.drop_index("idx_departments_parent_id", table_name="departments")
    op.drop_index("idx_departments_tenant_id", table_name="departments")
    op.drop_table("departments")
