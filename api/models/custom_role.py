import sqlalchemy as sa
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class Role(TypeBase):
    """Custom (non built-in) role used as an authorization subject."""

    __tablename__ = "kb_roles"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="kb_role_pkey"),
        sa.Index("idx_kb_roles_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    built_in: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False, onupdate=func.current_timestamp()
    )


class UserRole(TypeBase):
    """Binding between an account and a custom role within a tenant."""

    __tablename__ = "kb_user_roles"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="kb_user_role_pkey"),
        sa.Index("idx_kb_user_roles_user_id", "user_id"),
        sa.Index("idx_kb_user_roles_role_id", "role_id"),
        sa.Index("idx_kb_user_roles_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    user_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    role_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False
    )
