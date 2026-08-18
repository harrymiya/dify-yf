"""Department (org tree) service - CRUD helpers for the departments feature.

Part of customization P0 base: a tenant-scoped self-referencing org tree used
as an authorization subject in the four-layer KB permission model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import Department, DepartmentMember, KBPermissionGrant

if TYPE_CHECKING:
    pass


class DepartmentService:
    """CRUD and tree helpers for ``Department`` / ``DepartmentMember``."""

    @staticmethod
    def get_department(department_id: str, tenant_id: str, session: Session) -> Department | None:
        return session.scalar(
            select(Department).where(
                Department.id == department_id,
                Department.tenant_id == tenant_id,
            )
        )

    @staticmethod
    def create_department(
        *, tenant_id: str, name: str, parent_id: str | None = None, sort: int = 0, session: Session
    ) -> Department:
        department = Department(
            tenant_id=tenant_id,
            name=name,
            parent_id=parent_id,
            sort=sort,
        )
        session.add(department)
        session.flush()
        return department

    @staticmethod
    def update_department(
        department: Department, *, name: str | None = None, parent_id: str | None = None, sort: int | None = None
    ) -> None:
        if name is not None:
            department.name = name
        if parent_id is not None:
            department.parent_id = parent_id
        if sort is not None:
            department.sort = sort

    @staticmethod
    def has_cycle(department_id: str, new_parent_id: str | None, session: Session) -> bool:
        """Return True if setting ``new_parent_id`` would create a cycle.

        Re-parenting a department under itself or under one of its own
        descendants would break the tree; walk up from the new parent to the
        root and reject if we reach ``department_id``.
        """
        if not new_parent_id or new_parent_id == department_id:
            return new_parent_id == department_id
        cursor = new_parent_id
        visited: set[str] = set()
        while cursor and cursor not in visited:
            if cursor == department_id:
                return True
            visited.add(cursor)
            parent_id = session.scalar(select(Department.parent_id).where(Department.id == cursor))
            cursor = parent_id
        return False

    @staticmethod
    def delete_department(
        department_id: str, tenant_id: str, session: Session, *, cascade: bool = True
    ) -> int:
        """Delete a department and (optionally) its subtree; clears members.

        Returns the number of departments removed including the subtree.
        Returns 0 when the department does not exist in the tenant.
        """
        department = DepartmentService.get_department(department_id, tenant_id, session)
        if department is None:
            return 0

        ids_to_remove: list[str] = []
        frontier = [department_id]
        while frontier:
            current = frontier.pop()
            ids_to_remove.append(current)
            children = session.scalars(
                select(Department.id).where(
                    Department.tenant_id == tenant_id, Department.parent_id == current
                )
            )
            frontier.extend(str(c) for c in children)
            if not cascade:
                break

        session.execute(
            DepartmentMember.__table__.delete().where(
                DepartmentMember.department_id.in_(ids_to_remove)
            )
        )
        # Clean up authorization grants granted *to* the removed departments so they
        # do not leave dangling grants behind (default-deny model).
        session.execute(
            KBPermissionGrant.__table__.delete().where(
                KBPermissionGrant.tenant_id == tenant_id,
                KBPermissionGrant.subject_type == "department",
                KBPermissionGrant.subject_id.in_(ids_to_remove),
            )
        )
        session.execute(
            Department.__table__.delete().where(Department.id.in_(ids_to_remove))
        )
        return len(ids_to_remove)

    @staticmethod
    def add_member(department_id: str, account_id: str, tenant_id: str, session: Session) -> bool:
        existing = session.scalar(
            select(DepartmentMember.id).where(
                DepartmentMember.department_id == department_id,
                DepartmentMember.account_id == account_id,
                DepartmentMember.tenant_id == tenant_id,
            )
        )
        if existing:
            return False
        session.add(
            DepartmentMember(
                department_id=department_id,
                account_id=account_id,
                tenant_id=tenant_id,
            )
        )
        session.flush()
        return True

    @staticmethod
    def remove_member(department_id: str, account_id: str, tenant_id: str, session: Session) -> bool:
        result = session.execute(
            delete(DepartmentMember).where(
                DepartmentMember.department_id == department_id,
                DepartmentMember.account_id == account_id,
                DepartmentMember.tenant_id == tenant_id,
            )
        )
        return result.rowcount > 0

    @staticmethod
    def list_member_ids(department_id: str, tenant_id: str, session: Session) -> list[str]:
        rows = session.scalars(
            select(DepartmentMember.account_id).where(
                DepartmentMember.department_id == department_id,
                DepartmentMember.tenant_id == tenant_id,
            )
        )
        return [str(r) for r in rows]

    @staticmethod
    def build_tree(tenant_id: str, session: Session) -> list[dict]:
        """Return the full department tree as nested dicts for the tenant."""
        departments = session.scalars(
            select(Department).where(Department.tenant_id == tenant_id).order_by(Department.sort, Department.created_at)
        ).all()

        nodes: dict[str, dict] = {}
        for d in departments:
            nodes[d.id] = {
                "id": d.id,
                "tenant_id": d.tenant_id,
                "parent_id": d.parent_id,
                "name": d.name,
                "sort": d.sort,
                "children": [],
            }

        roots: list[dict] = []
        for node in nodes.values():
            pid = node["parent_id"]
            if pid and pid in nodes:
                nodes[pid]["children"].append(node)  # type: ignore[assignment]
            else:
                roots.append(node)
        return roots

    @staticmethod
    def list_member_account_ids_by_departments(department_ids: list[str], session: Session) -> set[str]:
        """All account ids that belong to any of the given departments."""
        if not department_ids:
            return set()
        rows = session.scalars(
            select(DepartmentMember.account_id).where(DepartmentMember.department_id.in_(department_ids))
        )
        return {str(r) for r in rows}
