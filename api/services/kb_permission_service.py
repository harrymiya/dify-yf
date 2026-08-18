"""KB permission service - four-layer authorization core.

Implements the customization requirement 3 (knowledge query permission) as an
**independent** authorization layer that does not touch the existing
community-edition ``dataset_permissions`` / ``check_dataset_permission`` model.

Grant model (subject x resource x action, default **deny**):

- subject  : account | department | role
- resource : dataset | document
- action   : a :class:`KBPermissionAction` operation

Department grants propagate to the department's members AND to all descendant
departments' members (a grant on a parent department applies down the tree).
See ``department_service.py`` for the tree helpers reused here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden

from models import (
    DepartmentMember,
    KBPermissionGrant,
    KBResourceType,
    KBSubjectType,
    UserRole,
)
from models.account import TenantAccountRole

if TYPE_CHECKING:
    from models import Account

logger = __import__("logging").getLogger(__name__)


class KBPermissionService:
    """Resolve and enforce four-layer knowledge permissions (default deny)."""

    # ------------------------------------------------------------------ #
    # Subject resolution
    # ------------------------------------------------------------------ #
    @staticmethod
    def list_group_member_department_ids(account_id: str, tenant_id: str, session: Session) -> set[str]:
        """Department ids the account directly belongs to."""
        rows = session.scalars(
            select(DepartmentMember.department_id).where(
                DepartmentMember.account_id == account_id, DepartmentMember.tenant_id == tenant_id
            )
        )
        return set(rows)

    @staticmethod
    def list_group_role_ids(account_id: str, tenant_id: str, session: Session) -> set[str]:
        """Custom role ids the account is bound to."""
        rows = session.scalars(
            select(UserRole.role_id).where(UserRole.user_id == account_id, UserRole.tenant_id == tenant_id)
        )
        return set(rows)

    @staticmethod
    def expand_ancestor_departments(
        department_ids: Iterable[str], tenant_id: str, session: Session
    ) -> set[str]:
        """Expand a set of department ids to include every ancestor up to a root.

        This implements parent-department inheritance: a grant on a parent
        department applies to members of all descendant departments.
        """
        from models import Department

        result: set[str] = set(department_ids)
        frontier: list[str] = list(department_ids)
        visited: set[str] = set()
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            parent_id = session.scalar(
                select(Department.parent_id).where(
                    Department.id == current, Department.tenant_id == tenant_id
                )
            )
            if parent_id and parent_id not in result:
                result.add(parent_id)
                frontier.append(parent_id)
        return result

    @staticmethod
    def resolve_subject_ids(account: "Account", session: Session) -> dict[KBSubjectType, set[str]]:
        """All subject ids that represent ``account`` for a grant match.

        Returns {account_id} plus every department the account belongs to
        (including ancestors, for parent-department inheritance) plus every
        custom role the account holds.
        """
        tenant_id = account.current_tenant_id
        if not tenant_id:
            return {}

        account_id = account.id
        department_ids = KBPermissionService.list_group_member_department_ids(account_id, tenant_id, session)
        expanded = KBPermissionService.expand_ancestor_departments(department_ids, tenant_id, session)
        role_ids = KBPermissionService.list_group_role_ids(account_id, tenant_id, session)

        return {
            KBSubjectType.ACCOUNT: {account_id},
            KBSubjectType.DEPARTMENT: expanded,
            KBSubjectType.ROLE: role_ids,
        }

    # ------------------------------------------------------------------ #
    # Grant / permission resolution
    # ------------------------------------------------------------------ #
    @staticmethod
    def resolve_effective_actions(
        account: "Account",
        *,
        resource_type: KBResourceType,
        resource_id: str,
        session: Session,
    ) -> set[str]:
        """Actions the account effectively holds on the given resource.

        Merges grants across all subject sources (own account, departments and
        their ancestors, custom roles). Returns an empty set when nothing is
        granted (i.e. the request is denied under default-deny).
        """
        tenant_id = account.current_tenant_id
        if not tenant_id:
            return set()

        subjects = KBPermissionService.resolve_subject_ids(account, session)
        actions: set[str] = set()
        for subject_type, subject_ids in subjects.items():
            if not subject_ids:
                continue
            rows = session.scalars(
                select(KBPermissionGrant.action).where(
                    KBPermissionGrant.tenant_id == tenant_id,
                    KBPermissionGrant.resource_type == resource_type.value,
                    KBPermissionGrant.resource_id == resource_id,
                    KBPermissionGrant.subject_type == subject_type.value,
                    KBPermissionGrant.subject_id.in_(subject_ids),
                )
            )
            actions.update(str(a) for a in rows)
        return actions

    @staticmethod
    def check_permission(
        account: "Account",
        *,
        resource_type: KBResourceType | str,
        resource_id: str,
        action: str,
        session: Session,
        allow_owner: bool = True,
    ) -> bool:
        """Return whether ``account`` may perform ``action`` on the resource.

        Default policy is **deny**. When ``allow_owner`` is true (default) an
        ``OWNER`` of the tenant is always granted, mirroring the community
        edition's owner short-circuit in ``check_dataset_permission``.
        """
        tenant_id = account.current_tenant_id
        if not tenant_id:
            return False
        # Owner and admin both hold privileged/management rights over the tenant.
        # Granting only the OWNER would lock workspace admins out of every un-validated
        # knowledge resource under the default-deny model (mirrors the community edition's
        # ``is_privileged_role`` semantics used by ``check_dataset_permission``).
        if allow_owner and TenantAccountRole.is_privileged_role(account.current_role):
            return True
        resource_type_enum = (
            resource_type if isinstance(resource_type, KBResourceType) else KBResourceType(resource_type)
        )
        actions = KBPermissionService.resolve_effective_actions(
            account, resource_type=resource_type_enum, resource_id=resource_id, session=session
        )
        return action in actions

    @staticmethod
    def require_permission(
        account: "Account",
        *,
        resource_type: KBResourceType | str,
        resource_id: str,
        action: str,
        session: Session,
        allow_owner: bool = True,
        message: str = "You do not have permission to access this resource.",
    ) -> None:
        """Raise :class:`Forbidden` unless ``account`` holds ``action``."""
        if not KBPermissionService.check_permission(
            account,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            session=session,
            allow_owner=allow_owner,
        ):
            raise Forbidden(message)

    @staticmethod
    def granted_resource_ids(
        account: "Account",
        *,
        resource_type: KBResourceType,
        action: str,
        session: Session,
    ) -> set[str] | None:
        """Ids of the given resource type the account can perform ``action`` on.

        Used for retrieval-layer whitelist injection (security baseline): an
        account may only touch resources present in this set. Returns ``None``
        when the account is unrestricted for ``action`` (e.g. the tenant owner).
        """
        tenant_id = account.current_tenant_id
        if not tenant_id:
            return set()
        # Owner/admin short-circuit: unrestricted access to every resource in the tenant.
        if TenantAccountRole.is_privileged_role(account.current_role):
            return None
        subjects = KBPermissionService.resolve_subject_ids(account, session)
        resource_ids: set[str] = set()
        for subject_type, subject_ids in subjects.items():
            if not subject_ids:
                continue
            rows = session.scalars(
                select(KBPermissionGrant.resource_id).where(
                    KBPermissionGrant.tenant_id == tenant_id,
                    KBPermissionGrant.resource_type == resource_type.value,
                    KBPermissionGrant.action == action,
                    KBPermissionGrant.subject_type == subject_type.value,
                    KBPermissionGrant.subject_id.in_(subject_ids),
                )
            )
            resource_ids.update(str(r) for r in rows)
        return resource_ids
