import sqlalchemy as sa
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class Department(TypeBase):
    """Org/department node in a tenant-scoped self-referencing tree."""

    __tablename__ = "departments"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="department_pkey"),
        sa.Index("idx_departments_tenant_id", "tenant_id"),
        sa.Index("idx_departments_parent_id", "parent_id"),
    )

    # NOTE: required (non-default) fields must precede optional (defaulted) fields
    # for the SQLAlchemy ``MappedAsDataclass`` constructor.
    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    parent_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    sort: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False, onupdate=func.current_timestamp()
    )


class DepartmentMember(TypeBase):
    """Binding between an account and a department."""

    __tablename__ = "department_members"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="department_member_pkey"),
        sa.Index("idx_department_members_department_id", "department_id"),
        sa.Index("idx_department_members_account_id", "account_id"),
        sa.Index("idx_department_members_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    department_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    account_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False
    )
