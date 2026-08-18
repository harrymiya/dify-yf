"""KB access-policy (grant) endpoints - customization requirement 3.

Manage four-layer authorization grants: grant an operation on a knowledge
resource (dataset / document) to a subject (account / department / role),
revoke them, and let the caller query their own effective permissions.
"""
from uuid import UUID

from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden, NotFound

from controllers.common.schema import register_schema_models
from controllers.common.session import with_session
from controllers.console import console_ns
from controllers.console.wraps import (
    account_initialization_required,
    model_validate,
    setup_required,
    with_current_tenant_id,
    with_current_user,
)
from libs.login import login_required
from models import (
    Account,
    Dataset,
    Department,
    Document,
    KBPermissionAction,
    KBPermissionGrant,
    KBResourceType,
    KBSubjectType,
    Role,
    TenantAccountJoin,
)
from models.account import TenantAccountRole
from models.audit_log import AuditLogStatus, AuditLogType
from services.audit_log_service import AuditLogService
from services.kb_permission_service import KBPermissionService


class GrantPayload(BaseModel):
    subject_type: KBSubjectType
    subject_id: str
    actions: list[KBPermissionAction] = Field(min_length=1)
    resource_type: KBResourceType = KBResourceType.DATASET
    resource_id: str


class GrantRevokePayload(BaseModel):
    subject_type: KBSubjectType
    subject_id: str
    resource_type: KBResourceType = KBResourceType.DATASET
    resource_id: str
    actions: list[KBPermissionAction] | None = None


register_schema_models(console_ns, GrantPayload, GrantRevokePayload)


def _require_updater(current_user: Account) -> None:
    if current_user.current_role not in (TenantAccountRole.OWNER, TenantAccountRole.ADMIN):
        raise Forbidden("Only the workspace owner or admin can manage knowledge access policies.")


def _subject_existence_check(subject_type: KBSubjectType, subject_id: str, tenant_id: str, session: Session) -> None:
    """Validate that the grant subject exists and belongs to the tenant."""
    if subject_type == KBSubjectType.ACCOUNT:
        binding = session.scalar(
            select(TenantAccountJoin.account_id).where(
                TenantAccountJoin.tenant_id == tenant_id,
                TenantAccountJoin.account_id == subject_id,
            )
        )
        if not binding:
            raise NotFound("account not found in this workspace")
    elif subject_type == KBSubjectType.DEPARTMENT:
        if session.get(Department, subject_id) is None or session.scalar(
            select(Department.tenant_id).where(Department.id == subject_id)
        ) != tenant_id:
            raise NotFound("department not found")
    elif subject_type == KBSubjectType.ROLE:
        if session.get(Role, subject_id) is None or session.scalar(
            select(Role.tenant_id).where(Role.id == subject_id)
        ) != tenant_id:
            raise NotFound("role not found")


def _resource_existence_check(resource_type: KBResourceType, resource_id: str, tenant_id: str, session: Session) -> None:
    """Validate that the grant resource (dataset/document) exists and belongs to the tenant."""
    if resource_type == KBResourceType.DOCUMENT:
        row = session.scalar(
            select(Document.dataset_id, Document.tenant_id).where(Document.id == resource_id)
        )
        if not row or row[1] != tenant_id:
            raise NotFound("document not found")
    else:
        row = session.scalar(select(Dataset.tenant_id).where(Dataset.id == resource_id))
        if not row or row != tenant_id:
            raise NotFound("dataset not found")


@console_ns.route("/workspaces/current/kb-permission-grants")
class KBPermissionGrantListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        resource_type = request.args.get("resource_type") or "dataset"
        resource_id = request.args.get("resource_id")
        query = select(KBPermissionGrant).where(
            KBPermissionGrant.tenant_id == current_tenant_id,
            KBPermissionGrant.resource_type == resource_type,
        )
        if resource_id:
            query = query.where(KBPermissionGrant.resource_id == resource_id)
        rows = session.scalars(query.order_by(KBPermissionGrant.created_at.desc())).all()
        data = [
            {
                "id": g.id,
                "subject_type": g.subject_type,
                "subject_id": g.subject_id,
                "resource_type": g.resource_type,
                "resource_id": g.resource_id,
                "action": g.action,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in rows
        ]
        return {"data": data}, 200

    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(GrantPayload)
    def post(self, req_data: GrantPayload, session: Session, current_tenant_id: str, current_user: Account):
        _require_updater(current_user)
        _subject_existence_check(req_data.subject_type, req_data.subject_id, current_tenant_id, session)
        _resource_existence_check(req_data.resource_type, req_data.resource_id, current_tenant_id, session)
        created = 0
        for action in req_data.actions:
            existing = session.scalar(
                select(KBPermissionGrant.id).where(
                    KBPermissionGrant.tenant_id == current_tenant_id,
                    KBPermissionGrant.subject_type == req_data.subject_type.value,
                    KBPermissionGrant.subject_id == req_data.subject_id,
                    KBPermissionGrant.resource_type == req_data.resource_type.value,
                    KBPermissionGrant.resource_id == req_data.resource_id,
                    KBPermissionGrant.action == action.value,
                )
            )
            if existing:
                continue
            session.add(
                KBPermissionGrant(
                    tenant_id=current_tenant_id,
                    subject_type=req_data.subject_type,
                    subject_id=req_data.subject_id,
                    resource_type=req_data.resource_type,
                    resource_id=req_data.resource_id,
                    action=action,
                    created_by=current_user.id,
                )
            )
            created += 1
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="kb_permission.grant",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type=req_data.resource_type.value,
            resource_id=req_data.resource_id,
            detail={
                "subject_type": req_data.subject_type.value,
                "subject_id": req_data.subject_id,
                "actions": [a.value for a in req_data.actions],
                "created": created,
            },
        )
        session.commit()
        return {"result": "success", "created": created}, 201


@console_ns.route("/workspaces/current/kb-permission-grants/revoke")
class KBPermissionGrantRevokeApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(GrantRevokePayload)
    def post(self, req_data: GrantRevokePayload, session: Session, current_tenant_id: str, current_user: Account):
        _require_updater(current_user)
        _resource_existence_check(req_data.resource_type, req_data.resource_id, current_tenant_id, session)
        where = [
            KBPermissionGrant.tenant_id == current_tenant_id,
            KBPermissionGrant.subject_type == req_data.subject_type.value,
            KBPermissionGrant.subject_id == req_data.subject_id,
            KBPermissionGrant.resource_type == req_data.resource_type.value,
            KBPermissionGrant.resource_id == req_data.resource_id,
        ]
        if req_data.actions is not None:
            where.append(KBPermissionGrant.action.in_([a.value for a in req_data.actions]))
        result = session.execute(delete(KBPermissionGrant).where(*where))
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="kb_permission.revoke",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type=req_data.resource_type.value,
            resource_id=req_data.resource_id,
            detail={
                "subject_type": req_data.subject_type.value,
                "subject_id": req_data.subject_id,
                "actions": [a.value for a in req_data.actions] if req_data.actions is not None else None,
                "removed": result.rowcount,
            },
        )
        session.commit()
        return {"result": "success", "removed": result.rowcount}, 200


@console_ns.route("/datasets/<uuid:dataset_id>/kb-my-permissions")
class KBMyPermissionsApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, dataset_id: UUID):
        actions = KBPermissionService.resolve_effective_actions(
            current_user,
            resource_type=KBResourceType.DATASET,
            resource_id=str(dataset_id),
            session=session,
        )
        return {"dataset_id": str(dataset_id), "actions": sorted(actions)}, 200
