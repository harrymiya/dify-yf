"""AuditLogService - persistence for the 5-class audit trail (requirement 5).

Records audit entries and reuses the request/trace/identity context exposed by
``core.logging`` so every row correlates with the structured application logs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.logging.context import get_identity_context, get_request_id, get_trace_id
from models import AuditLog, AuditLogStatus, AuditLogType

if TYPE_CHECKING:
    from werkzeug.datastructures import EnvironHeaders


class AuditLogService:
    """Write and read audit log entries."""

    @staticmethod
    def record(
        *,
        tenant_id: str,
        log_type: AuditLogType,
        action: str,
        session: Session,
        user_id: str | None = None,
        user_type: str | None = None,
        status: AuditLogStatus = AuditLogStatus.SUCCESS,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict[str, Any] | None = None,
        ip: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        """Insert one audit log row and return it (caller commits with its session)."""
        # Enrich from the current logging request context when not supplied.
        identity = get_identity_context()
        if not user_id:
            user_id = identity.user_id or None
        if not user_type:
            user_type = identity.user_type or None
        if not request_id:
            request_id = get_request_id() or None
        if not trace_id:
            trace_id = get_trace_id() or None

        entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            log_type=log_type,
            action=action,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip=ip,
            request_id=request_id,
            trace_id=trace_id,
        )
        session.add(entry)
        return entry

    @staticmethod
    def query(
        session: Session,
        *,
        tenant_id: str,
        log_type: AuditLogType | None = None,
        action: str | None = None,
        resource_id: str | None = None,
        user_id: str | None = None,
        status: AuditLogStatus | None = None,
        before: Any = None,  # datetime
        after: Any = None,  # datetime
        offset: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Query audit logs for a tenant with optional filters, newest first."""
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if log_type is not None:
            stmt = stmt.where(AuditLog.log_type == log_type.value)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if status is not None:
            stmt = stmt.where(AuditLog.status == status.value)
        if after is not None:
            stmt = stmt.where(AuditLog.created_at >= after)
        if before is not None:
            stmt = stmt.where(AuditLog.created_at <= before)
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        return list(session.scalars(stmt).all())

    @staticmethod
    def enrich_from_headers(
        *,
        tenant_id: str,
        log_type: AuditLogType,
        action: str,
        session: Session,
        headers: "EnvironHeaders | dict[str, str] | None" = None,
        **kwargs: Any,
    ) -> AuditLog:
        """Record an audit entry, extracting the client IP from request headers."""
        ip: str | None = None
        if headers:
            forwarded = headers.get("X-Forwarded-For") if isinstance(headers, dict) else headers.get("X-Forwarded-For")
            if forwarded:
                ip = str(forwarded).split(",")[0].strip() or None
            if not ip:
                ip = headers.get("X-Real-IP") or headers.get("Remote-Addr") or None
                if isinstance(ip, str):
                    ip = ip.strip() or None
        return AuditLogService.record(
            tenant_id=tenant_id,
            log_type=log_type,
            action=action,
            session=session,
            ip=ip,
            **kwargs,
        )
