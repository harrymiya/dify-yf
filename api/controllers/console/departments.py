"""Department (org tree) management endpoints - P0 base.

Implements department tree CRUD plus member management. Departments are used as
an authorization subject in the four-layer KB permission model.
"""
from uuid import UUID

from flask_restx import Resource
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, NotFound

from controllers.common.fields import SimpleResultDataResponse
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
from models import Account
from models.audit_log import AuditLogStatus, AuditLogType
from services.audit_log_service import AuditLogService
from services.department_service import DepartmentService


class DepartmentCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    parent_id: str | None = None
    sort: int = 0


class DepartmentUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    parent_id: str | None = None
    sort: int | None = None


class DepartmentMemberAddPayload(BaseModel):
    account_ids: list[str] = Field(min_length=1)


register_schema_models(console_ns, DepartmentCreatePayload, DepartmentUpdatePayload, DepartmentMemberAddPayload)


@console_ns.route("/workspaces/current/departments")
class DepartmentListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        tree = DepartmentService.build_tree(current_tenant_id, session)
        return {"data": tree}, 200

    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(DepartmentCreatePayload)
    def post(self, req_data: DepartmentCreatePayload, session: Session, current_tenant_id: str, current_user: Account):
        if req_data.parent_id:
            parent = DepartmentService.get_department(req_data.parent_id, current_tenant_id, session)
            if parent is None:
                raise NotFound("parent department not found")
        department = DepartmentService.create_department(
            tenant_id=current_tenant_id,
            name=req_data.name,
            description=req_data.description,
            parent_id=req_data.parent_id,
            sort=req_data.sort,
            session=session,
        )
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="department.create",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="department",
            resource_id=department.id,
            detail={"name": req_data.name, "description": req_data.description, "parent_id": req_data.parent_id},
        )
        session.commit()
        return SimpleResultDataResponse(result="success", data=department.id).model_dump(mode="json"), 201


@console_ns.route("/workspaces/current/departments/<uuid:department_id>")
class DepartmentDetailApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, department_id: UUID):
        department = DepartmentService.get_department(str(department_id), current_tenant_id, session)
        if department is None:
            raise NotFound("department not found")
        return {
            "id": department.id,
            "parent_id": department.parent_id,
            "name": department.name,
            "description": department.description,
            "sort": department.sort,
        }, 200

    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(DepartmentUpdatePayload)
    def patch(
        self, req_data: DepartmentUpdatePayload, session: Session, current_tenant_id: str, current_user: Account, department_id: UUID
    ):
        department = DepartmentService.get_department(str(department_id), current_tenant_id, session)
        if department is None:
            raise NotFound("department not found")
        if req_data.parent_id is not None and DepartmentService.has_cycle(
            str(department_id), req_data.parent_id, session
        ):
            raise BadRequest("cannot re-parent a department under itself or a descendant")
        DepartmentService.update_department(
            department,
            name=req_data.name,
            description=req_data.description,
            parent_id=req_data.parent_id,
            sort=req_data.sort,
        )
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="department.update",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="department",
            resource_id=str(department_id),
            detail={
                "name": req_data.name,
                "description": req_data.description,
                "parent_id": req_data.parent_id,
                "sort": req_data.sort,
            },
        )
        session.commit()
        return {"result": "success"}, 200

    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    def delete(self, session: Session, current_tenant_id: str, current_user: Account, department_id: UUID):
        count = DepartmentService.delete_department(str(department_id), current_tenant_id, session)
        if count == 0:
            raise NotFound("department not found")
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="department.delete",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="department",
            resource_id=str(department_id),
            detail={"removed_subtree": count},
        )
        session.commit()
        return {"result": "success"}, 200


@console_ns.route("/workspaces/current/departments/<uuid:department_id>/members")
class DepartmentMemberListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, department_id: UUID):
        if DepartmentService.get_department(str(department_id), current_tenant_id, session) is None:
            raise NotFound("department not found")
        member_ids = DepartmentService.list_member_ids(str(department_id), current_tenant_id, session)
        return {"data": member_ids}, 200

    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(DepartmentMemberAddPayload)
    def post(self, req_data: DepartmentMemberAddPayload, session: Session, current_tenant_id: str, current_user: Account, department_id: UUID):
        if DepartmentService.get_department(str(department_id), current_tenant_id, session) is None:
            raise NotFound("department not found")
        for account_id in req_data.account_ids:
            DepartmentService.add_member(str(department_id), account_id, current_tenant_id, session)
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.PERMISSION_CHANGE,
            action="department.add_members",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="department",
            resource_id=str(department_id),
            detail={"account_ids": req_data.account_ids},
        )
        session.commit()
        return {"result": "success"}, 200
