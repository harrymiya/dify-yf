"""Audit log model - customization requirement 5.

Persists a unified audit trail across 5 event classes (Q&A, retrieval,
document download, permission change, system) so operators can review who did
what on knowledge resources. Reuses the request context from ``core.logging``
(request/trace/identity) to correlate with the structured application logs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class AuditLogType(StrEnum):
    """Five audit event classes (requirement 5)."""

    QNA = "qna"  # Q&A conversation / assistant reply
    RETRIEVAL = "retrieval"  # knowledge retrieval / hit-testing
    DOWNLOAD = "download"  # original document download
    PERMISSION_CHANGE = "permission_change"  # KB grant / revoke / role or dept change
    SYSTEM = "system"  # system / config events


class AuditLogStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(TypeBase):
    """One audit event row."""

    __tablename__ = "kb_audit_logs"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="kb_audit_log_pkey"),
        Index("idx_kb_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("idx_kb_audit_logs_tenant_type", "tenant_id", "log_type"),
    )

    # NOTE: required (non-default) fields must precede optional (defaulted) fields
    # for the SQLAlchemy ``MappedAsDataclass`` constructor.
    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    log_type: Mapped[AuditLogType] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    user_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)  # account / end-user / system
    status: Mapped[AuditLogStatus] = mapped_column(String(16), nullable=False, default=AuditLogStatus.SUCCESS)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)  # dataset / document / app
    resource_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    detail: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True, default=None)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True, default=None)
    request_id: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id!r} tenant={self.tenant_id!r} type={self.log_type!r} "
            f"action={self.action!r} status={self.status!r}>"
        )
