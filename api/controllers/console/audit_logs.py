"""Audit log query endpoints - customization requirement 5.

Read-side API for the 5-class audit trail with tenant scoping, filters
(log type / action / resource / user / status / time range / department) and
pagination. Only the tenant owner or admin may read audit logs.
"""

from uuid import UUID

from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Forbidden

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


def _is_valid_uuid(value: str) -> bool:
    """Return True only for a well-formed UUID string."""
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


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

        department_id = request.args.get("department_id") or None
        member_account_ids = None
        if department_id:
            if not _is_valid_uuid(department_id):
                raise BadRequest("department_id must be a valid UUID.")
            member_account_ids = AuditLogService.resolve_department_member_account_ids(
                session, tenant_id=current_tenant_id, department_id=department_id
            )

        rows = AuditLogService.query(
            session,
            tenant_id=current_tenant_id,
            log_type=type_enum,
            action=action,
            resource_id=resource_id,
            user_id=user_id,
            status=status_enum,
            member_account_ids=member_account_ids,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        total = AuditLogService.count(
            session,
            tenant_id=current_tenant_id,
            log_type=type_enum,
            action=action,
            resource_id=resource_id,
            user_id=user_id,
            status=status_enum,
            member_account_ids=member_account_ids,
        )

        user_ids = {r.user_id for r in rows if r.user_id}
        accounts, account_departments = AuditLogService.load_account_enrichment(
            session, tenant_id=current_tenant_id, account_ids=user_ids
        )

        def _enrich(row: AuditLog) -> dict:
            user_name = None
            user_email = None
            department_ids: list[str] = []
            department_names: list[str] = []
            if row.user_id:
                if row.user_id in accounts:
                    user_name, user_email = accounts[row.user_id]
                for dept_id, dept_name in account_departments.get(row.user_id, []):
                    department_ids.append(dept_id)
                    department_names.append(dept_name)
            return {
                "id": row.id,
                "user_id": row.user_id,
                "user_type": row.user_type,
                "user_name": user_name,
                "user_email": user_email,
                "department_ids": department_ids,
                "department_names": department_names,
                "log_type": row.log_type,
                "action": row.action,
                "status": row.status,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "detail": row.detail,
                "ip": row.ip,
                "request_id": row.request_id,
                "trace_id": row.trace_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

        data = [_enrich(r) for r in rows]
        return {"data": data, "total": total, "page": page, "page_size": page_size}, 200
