"""Audit log query endpoints - customization requirement 5.

Read-side API for the 5-class audit trail with tenant scoping, filters
(log type / action / resource / user / status / time range) and pagination.
Only the tenant owner or admin may read audit logs.
"""

from flask_restx import Resource
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden

from controllers.common.session import with_session
from controllers.console import console_ns
from controllers.console.wraps import (
    account_initialization_required,
    setup_required,
    with_current_tenant_id,
    with_current_user,
)
from libs.login import login_required
from models import Account, AuditLog, AuditLogType
from models.account import TenantAccountRole
from services.audit_log_service import AuditLogService


@console_ns.route("/workspaces/current/audit-logs")
class AuditLogListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        if current_user.current_role not in (TenantAccountRole.OWNER, TenantAccountRole.ADMIN):
            raise Forbidden("Only the workspace owner or admin can read audit logs.")

        from flask import request

        log_type = request.args.get("log_type") or None
        action = request.args.get("action") or None
        resource_id = request.args.get("resource_id") or None
        user_id = request.args.get("user_id") or None
        status = request.args.get("status") or None
        page = max(int(request.args.get("page", 1) or 1), 1)
        page_size = min(max(int(request.args.get("page_size", 20) or 20), 1), 200)

        type_enum = None
        if log_type:
            try:
                type_enum = AuditLogType(log_type)
            except ValueError:
                type_enum = None

        status_enum = None
        if status in {"success", "failure"}:
            from models import AuditLogStatus

            status_enum = AuditLogStatus(status)

        rows = AuditLogService.query(
            session,
            tenant_id=current_tenant_id,
            log_type=type_enum,
            action=action,
            resource_id=resource_id,
            user_id=user_id,
            status=status_enum,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        total = session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.tenant_id == current_tenant_id)
        ) or 0

        data = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_type": r.user_type,
                "log_type": r.log_type,
                "action": r.action,
                "status": r.status,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "ip": r.ip,
                "request_id": r.request_id,
                "trace_id": r.trace_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"data": data, "total": total, "page": page, "page_size": page_size}, 200
