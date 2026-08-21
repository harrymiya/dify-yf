"""AuditLogService - persistence for the 5-class audit trail (requirement 5).

Records audit entries and reuses the request/trace/identity context exposed by
``core.logging`` so every row correlates with the structured application logs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.logging.context import get_identity_context, get_request_id, get_trace_id
from models import Account, AuditLog, AuditLogStatus, AuditLogType, Department, DepartmentMember

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
        member_account_ids: set[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Query audit logs for a tenant with optional filters, newest first.

        ``member_account_ids`` is an optional set of account IDs (resolved from a
        department subtree) that limits results to logs whose ``user_id`` is one of
        them.
        """
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
        if member_account_ids is not None:
            stmt = stmt.where(AuditLog.user_id.in_(member_account_ids))
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        return list(session.scalars(stmt).all())

    @staticmethod
    def count(
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
        member_account_ids: set[str] | None = None,
    ) -> int:
        """Count audit logs applying the same filters as :meth:`query` (no pagination)."""
        from sqlalchemy import func

        stmt = select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
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
        if member_account_ids is not None:
            stmt = stmt.where(AuditLog.user_id.in_(member_account_ids))
        return session.scalar(stmt) or 0

    @staticmethod
    def resolve_department_member_account_ids(
        session: Session, *, tenant_id: str, department_id: str
    ) -> set[str]:
        """Resolve all account IDs that belong to a department subtree.

        Loads the tenant's department tree, computes the given department plus all
        of its descendants (parent contains child), then collects every
        ``department_members.account_id`` bound to any of those departments.
        Returns an empty set when the department does not exist in the tenant.
        """
        departments = list(
            session.scalars(select(Department).where(Department.tenant_id == tenant_id)).all()
        )
        by_id = {d.id: d for d in departments}
        if department_id not in by_id:
            return set()

        children: dict[str, list[str]] = {}
        for d in departments:
            children.setdefault(d.parent_id or "", []).append(d.id)

        subtree = {department_id}
        stack = [department_id]
        while stack:
            node = stack.pop()
            for child in children.get(node, []):
                if child not in subtree:
                    subtree.add(child)
                    stack.append(child)

        member_rows = session.scalars(
            select(DepartmentMember.account_id).where(
                DepartmentMember.tenant_id == tenant_id,
                DepartmentMember.department_id.in_(subtree),
            )
        ).all()
        return set(member_rows)

    @staticmethod
    def load_account_enrichment(
        session: Session, *, tenant_id: str, account_ids: set[str]
    ) -> tuple[dict[str, tuple[str | None, str | None]], dict[str, list[tuple[str, str]]]]:
        """Batch-load account (name, email) and account -> departments maps.

        Returns ``(accounts, departments)`` where:
        - ``accounts``: account_id -> (name, email) for existing accounts.
        - ``departments``: account_id -> ordered list of (department_id, department_name).
        No N+1: accounts and department bindings are loaded in a small number of
        batch queries. Everything is scoped to ``tenant_id`` so no account or
        department belonging to another tenant leaks into the result.
        """
        from models import TenantAccountJoin

        accounts: dict[str, tuple[str | None, str | None]] = {}
        departments: dict[str, list[tuple[str, str]]] = {}
        if not account_ids:
            return accounts, departments

        # Accounts: only those that are members of this tenant.
        tenant_account_rows = session.scalars(
            select(TenantAccountJoin.account_id).where(
                TenantAccountJoin.tenant_id == tenant_id,
                TenantAccountJoin.account_id.in_(account_ids),
            )
        ).all()
        tenant_account_ids = set(tenant_account_rows)
        if tenant_account_ids:
            acct_rows = session.scalars(
                select(Account).where(Account.id.in_(tenant_account_ids))
            ).all()
            for acct in acct_rows:
                accounts[acct.id] = (acct.name, acct.email)

        # Department memberships: only rows in this tenant.
        member_rows = session.execute(
            select(DepartmentMember.department_id, DepartmentMember.account_id).where(
                DepartmentMember.tenant_id == tenant_id,
                DepartmentMember.account_id.in_(account_ids),
            )
        ).all()
        dept_ids = {dept_id for dept_id, _acct in member_rows}
        dept_names: dict[str, str] = {}
        if dept_ids:
            dept_rows = session.scalars(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.id.in_(dept_ids),
                )
            ).all()
            dept_names = {d.id: d.name for d in dept_rows}
        for dept_id, acct_id in member_rows:
            departments.setdefault(acct_id, []).append((dept_id, dept_names.get(dept_id, "")))

        return accounts, departments

    @staticmethod
    def enrich_from_headers(
        *,
        tenant_id: str,
        log_type: AuditLogType,
        action: str,
        session: Session,
        headers: EnvironHeaders | dict[str, str] | None = None,
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
