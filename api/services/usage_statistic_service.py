"""UsageStatisticService - metering & statistics (requirement 4, task D4).

Aggregates knowledge-base call volume and interface call volume for the
operator dashboard. It reuses the authoritative existing data instead of a
duplicate counter table:

- knowledge-base calls: ``dataset_queries`` (every hit-testing and app
  retrieval already inserts a row keyed by ``dataset_id``/``source``).
- interface / event calls: ``audit_logs`` (requirement 5) keyed by action/type.
- time trend: bucketed counts over either source.

The OPS trace id captured on ``audit_logs`` correlates rows with ``core.ops``
structured telemetry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Account, App, AuditLog, CreatorUserRole, DatasetQuery

if TYPE_CHECKING:
    pass

# Virtual bucket identifiers used by per-user / per-department aggregation.
# These are not real accounts or departments and are always returned last.
_BUCKET_EXTERNAL_API = "__external_api__"
_BUCKET_UNKNOWN = "__unknown__"
_BUCKET_UNASSIGNED = "__unassigned__"
_BUCKET_UNKNOWN_SYSTEM = "__unknown_system__"

# Display names for the virtual buckets (kept in Chinese to match the UI).
_VIRTUAL_BUCKET_NAMES = {
    _BUCKET_EXTERNAL_API: "外部调用 / API",
    _BUCKET_UNKNOWN: "未知账号",
    _BUCKET_UNASSIGNED: "未分配",
    _BUCKET_UNKNOWN_SYSTEM: "未知 / 系统",
}


class UsageStatisticService:
    """Aggregate usage statistics for a tenant."""

    @staticmethod
    def kb_call_top(
        session: Session,
        *,
        tenant_id: str,
        dataset_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Knowledge-base call counts per dataset, descending (Top N).

        ``dataset_queries`` is scoped per tenant via its owning dataset; we join
        through the datasets the tenant owns (the rows' ``created_by`` is the
        tenant account, but the authoritative tenant link is the dataset).
        """
        # dataset_queries has no tenant_id column; restrict via owning datasets.
        from models import Dataset

        tenant_ds = session.scalars(
            select(Dataset.id).where(Dataset.tenant_id == tenant_id)
        ).all()
        tenant_ds_set = set(tenant_ds)
        if dataset_ids is not None:
            tenant_ds_set = tenant_ds_set & set(dataset_ids)
        if not tenant_ds_set:
            return []

        stmt = (
            select(
                DatasetQuery.dataset_id,
                func.count(DatasetQuery.id).label("total"),
            )
            .where(DatasetQuery.dataset_id.in_(tenant_ds_set))
            .group_by(DatasetQuery.dataset_id)
            .order_by(func.count(DatasetQuery.id).desc())
            .limit(limit)
        )
        if start_time is not None:
            stmt = stmt.where(DatasetQuery.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(DatasetQuery.created_at <= end_time)

        rows = session.execute(stmt).all()
        return [{"dataset_id": str(r[0]), "calls": int(r[1] or 0)} for r in rows]

    # ------------------------------------------------------------------ #
    # Private helpers (fetch + attribution building blocks).
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tenant_dataset_id_set(
        session: Session, *, tenant_id: str, dataset_ids: list[str] | None = None
    ) -> set[str]:
        from models import Dataset

        owned = set(session.scalars(select(Dataset.id).where(Dataset.tenant_id == tenant_id)).all())
        if dataset_ids is not None:
            owned = owned & {str(d) for d in dataset_ids}
        return set(owned)

    @staticmethod
    def _fetch_kb_query_rows(
        session: Session, *, dataset_ids: set[str], start_time: datetime | None, end_time: datetime | None
    ) -> list[tuple]:
        """Each ``dataset_queries`` row is one KB call; return the attribution fields."""
        stmt = select(
            DatasetQuery.created_by_role,
            DatasetQuery.created_by,
            DatasetQuery.source_app_id,
        ).where(DatasetQuery.dataset_id.in_(dataset_ids))
        if start_time is not None:
            stmt = stmt.where(DatasetQuery.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(DatasetQuery.created_at <= end_time)
        return session.execute(stmt).all()

    @staticmethod
    def _apps_created_by(session: Session, *, tenant_id: str, app_ids: set[str]) -> dict[str, str]:
        """Map app id -> responsible account id, tenant-scoped (App.created_by)."""
        if not app_ids:
            return {}
        rows = session.execute(
            select(App.id, App.created_by).where(App.tenant_id == tenant_id, App.id.in_(app_ids))
        ).all()
        return {str(r[0]): r[1] for r in rows if r[1]}

    @staticmethod
    def _accounts_name_email(session: Session, *, account_ids: set[str]) -> dict[str, dict[str, Any]]:
        if not account_ids:
            return {}
        rows = session.execute(
            select(Account.id, Account.name, Account.email).where(Account.id.in_(account_ids))
        ).all()
        return {str(r[0]): {"name": r[1], "email": r[2]} for r in rows}

    @staticmethod
    def _tenant_account_ids(session: Session, *, tenant_id: str) -> set[str]:
        from models import TenantAccountJoin

        return set(
            session.scalars(
                select(TenantAccountJoin.account_id).where(TenantAccountJoin.tenant_id == tenant_id)
            ).all()
        )

    @staticmethod
    def _account_departments(
        session: Session, *, tenant_id: str, account_ids: set[str]
    ) -> dict[str, set[str]]:
        """Map account id -> set of department ids (direct + all ancestors)."""
        from models import Department, DepartmentMember

        if not account_ids:
            return {}

        member_rows = session.execute(
            select(DepartmentMember.account_id, DepartmentMember.department_id).where(
                DepartmentMember.tenant_id == tenant_id,
                DepartmentMember.account_id.in_(account_ids),
            )
        ).all()
        # direct memberships per account
        direct: dict[str, list[str]] = {}
        for account_id, dept_id in member_rows:
            direct.setdefault(str(account_id), []).append(str(dept_id))

        # parent chain for all tenant departments (used for ancestor fan-out)
        dept_rows = session.execute(
            select(Department.id, Department.parent_id).where(Department.tenant_id == tenant_id)
        ).all()
        parents = {str(d[0]): str(d[1]) if d[1] else None for d in dept_rows}

        result: dict[str, set[str]] = {}
        for account_id, dept_ids in direct.items():
            expanded: set[str] = set()
            for dept_id in dept_ids:
                cur: str | None = dept_id
                while cur:
                    if cur in expanded:
                        break
                    expanded.add(cur)
                    cur = parents.get(cur)
            result[account_id] = expanded
        return result

    @staticmethod
    def _department_info_map(
        session: Session, *, tenant_id: str, dept_ids: set[str]
    ) -> dict[str, dict[str, Any]]:
        from models import Department

        if not dept_ids:
            return {}
        rows = session.execute(
            select(Department.id, Department.name, Department.parent_id).where(
                Department.tenant_id == tenant_id, Department.id.in_(dept_ids)
            )
        ).all()
        return {
            str(r[0]): {"name": r[1], "parent_id": str(r[2]) if r[2] else None}
            for r in rows
        }

    @staticmethod
    def _resolve_kb_account(
        role: Any,
        created_by: str,
        source_app_id: str | None,
        *,
        app_map: dict[str, str],
        tenant_account_set: set[str],
    ) -> str:
        """Resolve the attribution account for one KB call (see plan section 1.1)."""
        role = str(role) if role is not None else ""
        if role == CreatorUserRole.ACCOUNT.value:
            account_id = str(created_by)
            return account_id if account_id in tenant_account_set else _BUCKET_UNKNOWN
        # end_user: attribute to the App owner when resolvable in-tenant.
        responsible = app_map.get(str(source_app_id)) if source_app_id else None
        if responsible:
            account_id = str(responsible)
            return account_id if account_id in tenant_account_set else _BUCKET_UNKNOWN
        return _BUCKET_EXTERNAL_API

    @staticmethod
    def _aggregate_kb_by_account(
        rows: list[tuple],
        *,
        app_map: dict[str, str],
        tenant_account_set: set[str],
    ) -> dict[str, int]:
        totals: dict[str, int] = {}
        for row in rows:
            role, created_by, source_app_id = row[0], row[1], row[2]
            account_id = UsageStatisticService._resolve_kb_account(
                role,
                str(created_by),
                str(source_app_id) if source_app_id else None,
                app_map=app_map,
                tenant_account_set=tenant_account_set,
            )
            totals[account_id] = totals.get(account_id, 0) + 1
        return totals

    @staticmethod
    def _sort_and_limit(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        """Virtual buckets always last; within each group calls DESC, same calls by real name ASC."""
        items = sorted(
            items,
            key=lambda x: (
                1 if x["is_virtual"] else 0,
                -x["calls"],
                (x.get("name") or "") or "",
            ),
        )
        return items[:limit]

    @staticmethod
    def _build_user_items(
        totals: dict[str, int], *, account_map: dict[str, dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for account_id, calls in totals.items():
            if account_id in _VIRTUAL_BUCKET_NAMES:
                items.append(
                    {
                        "id": account_id,
                        "name": _VIRTUAL_BUCKET_NAMES[account_id],
                        "email": None,
                        "is_virtual": True,
                        "calls": calls,
                    }
                )
                continue
            info = account_map.get(account_id, {})
            items.append(
                {
                    "id": account_id,
                    "name": info.get("name") or account_id,
                    "email": info.get("email"),
                    "is_virtual": False,
                    "calls": calls,
                }
            )
        return UsageStatisticService._sort_and_limit(items, limit=limit)

    @staticmethod
    def _department_calls(
        totals: dict[str, int],
        *,
        member_departments: dict[str, set[str]],
        virtual_buckets: set[str],
    ) -> dict[str, int]:
        """Fan account totals out to direct + ancestor departments (父含子孙)."""
        dept_totals: dict[str, int] = {}
        for entity, calls in totals.items():
            if entity in virtual_buckets:
                dept_totals[entity] = dept_totals.get(entity, 0) + calls
                continue
            depts = member_departments.get(entity)
            if depts:
                for d in depts:
                    dept_totals[d] = dept_totals.get(d, 0) + calls
            else:
                dept_totals[_BUCKET_UNASSIGNED] = dept_totals.get(_BUCKET_UNASSIGNED, 0) + calls
        return dept_totals

    @staticmethod
    def _build_department_items(
        dept_totals: dict[str, int],
        *,
        dept_info: dict[str, dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for dept_id, calls in dept_totals.items():
            if dept_id in _VIRTUAL_BUCKET_NAMES:
                items.append(
                    {
                        "id": dept_id,
                        "name": _VIRTUAL_BUCKET_NAMES[dept_id],
                        "parent_id": None,
                        "is_virtual": True,
                        "calls": calls,
                    }
                )
                continue
            info = dept_info.get(dept_id, {})
            items.append(
                {
                    "id": dept_id,
                    "name": info.get("name") or dept_id,
                    "parent_id": info.get("parent_id"),
                    "is_virtual": False,
                    "calls": calls,
                }
            )
        return UsageStatisticService._sort_and_limit(items, limit=limit)

    @staticmethod
    def _department_payload(
        account_totals: dict[str, int],
        *,
        session: Session,
        tenant_id: str,
        virtual_buckets: set[str],
        limit: int,
    ) -> dict[str, Any]:
        member_departments = UsageStatisticService._account_departments(
            session, tenant_id=tenant_id, account_ids=set(account_totals.keys())
        )
        dept_totals = UsageStatisticService._department_calls(
            account_totals, member_departments=member_departments, virtual_buckets=virtual_buckets
        )
        real_ids = set(dept_totals.keys()) - virtual_buckets
        dept_info = UsageStatisticService._department_info_map(
            session, tenant_id=tenant_id, dept_ids=real_ids
        )
        data = UsageStatisticService._build_department_items(
            dept_totals, dept_info=dept_info, limit=limit
        )
        return {
            "dimension": "department",
            "total_calls": sum(account_totals.values()),
            "grouped_calls": sum(dept_totals.values()),
            "aggregation": "include_descendants",
            "data": data,
        }

    # ------------------------------------------------------------------ #
    # Per-user / per-department aggregation.
    # ------------------------------------------------------------------ #

    @staticmethod
    def kb_call_top_by_user(
        session: Session,
        *,
        tenant_id: str,
        dataset_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """KB calls attributed per account (plan section 1.1 / 2)."""
        tenant_ds = UsageStatisticService._tenant_dataset_id_set(
            session, tenant_id=tenant_id, dataset_ids=dataset_ids
        )
        if not tenant_ds:
            return {"dimension": "user", "total_calls": 0, "data": []}

        rows = UsageStatisticService._fetch_kb_query_rows(
            session, dataset_ids=tenant_ds, start_time=start_time, end_time=end_time
        )
        app_ids = {str(r[2]) for r in rows if r[2]}
        app_map = UsageStatisticService._apps_created_by(session, tenant_id=tenant_id, app_ids=app_ids)
        tenant_account_set = UsageStatisticService._tenant_account_ids(session, tenant_id=tenant_id)
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map=app_map, tenant_account_set=tenant_account_set
        )
        account_map = UsageStatisticService._accounts_name_email(
            session,
            account_ids={a for a in totals if a not in _VIRTUAL_BUCKET_NAMES},
        )
        data = UsageStatisticService._build_user_items(totals, account_map=account_map, limit=limit)
        return {
            "dimension": "user",
            "total_calls": sum(totals.values()),
            "data": data,
        }

    @staticmethod
    def kb_call_top_by_department(
        session: Session,
        *,
        tenant_id: str,
        dataset_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """KB calls attributed per department incl. ancestors (plan section 1.1 / 2)."""
        tenant_ds = UsageStatisticService._tenant_dataset_id_set(
            session, tenant_id=tenant_id, dataset_ids=dataset_ids
        )
        if not tenant_ds:
            return {
                "dimension": "department",
                "total_calls": 0,
                "grouped_calls": 0,
                "aggregation": "include_descendants",
                "data": [],
            }

        rows = UsageStatisticService._fetch_kb_query_rows(
            session, dataset_ids=tenant_ds, start_time=start_time, end_time=end_time
        )
        app_ids = {str(r[2]) for r in rows if r[2]}
        app_map = UsageStatisticService._apps_created_by(session, tenant_id=tenant_id, app_ids=app_ids)
        tenant_account_set = UsageStatisticService._tenant_account_ids(session, tenant_id=tenant_id)
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map=app_map, tenant_account_set=tenant_account_set
        )
        return UsageStatisticService._department_payload(
            totals,
            session=session,
            tenant_id=tenant_id,
            virtual_buckets={_BUCKET_EXTERNAL_API, _BUCKET_UNKNOWN},
            limit=limit,
        )

    @staticmethod
    def interface_call_top_by_user(
        session: Session,
        *,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Interface/event calls attributed per account (plan section 1.2 / 2)."""
        stmt = (
            select(AuditLog.user_id, func.count(AuditLog.id).label("total"))
            .where(AuditLog.tenant_id == tenant_id)
            .group_by(AuditLog.user_id)
        )
        if start_time is not None:
            stmt = stmt.where(AuditLog.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.created_at <= end_time)
        rows = session.execute(stmt).all()

        tenant_account_set = UsageStatisticService._tenant_account_ids(session, tenant_id=tenant_id)
        involved = {str(r[0]) for r in rows if r[0]}
        account_map = (
            UsageStatisticService._accounts_name_email(session, account_ids=involved) if involved else {}
        )
        total_calls = 0
        item_totals: dict[str, dict[str, Any]] = {}
        for user_id, calls in rows:
            calls = int(calls or 0)
            total_calls += calls
            if not user_id:
                key = _BUCKET_UNKNOWN_SYSTEM
                item_totals.setdefault(
                    key,
                    {
                        "id": key,
                        "name": _VIRTUAL_BUCKET_NAMES[key],
                        "email": None,
                        "is_virtual": True,
                        "calls": 0,
                    },
                )["calls"] += calls
            elif str(user_id) in tenant_account_set:
                info = account_map.get(str(user_id), {})
                item_totals[str(user_id)] = {
                    "id": str(user_id),
                    "name": info.get("name") or str(user_id),
                    "email": info.get("email"),
                    "is_virtual": False,
                    "calls": calls,
                }
            else:
                key = _BUCKET_UNKNOWN
                item_totals.setdefault(
                    key,
                    {
                        "id": key,
                        "name": _VIRTUAL_BUCKET_NAMES[key],
                        "email": None,
                        "is_virtual": True,
                        "calls": 0,
                    },
                )["calls"] += calls
        data = UsageStatisticService._sort_and_limit(list(item_totals.values()), limit=limit)
        return {"dimension": "user", "total_calls": total_calls, "data": data}

    @staticmethod
    def interface_call_top_by_department(
        session: Session,
        *,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Interface/event calls attributed per department incl. ancestors (plan 1.2 / 2)."""
        account_totals: dict[str, int] = {}
        virtual_totals: dict[str, int] = {}

        stmt = (
            select(AuditLog.user_id, func.count(AuditLog.id).label("total"))
            .where(AuditLog.tenant_id == tenant_id)
            .group_by(AuditLog.user_id)
        )
        if start_time is not None:
            stmt = stmt.where(AuditLog.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.created_at <= end_time)
        rows = session.execute(stmt).all()

        tenant_account_set = UsageStatisticService._tenant_account_ids(session, tenant_id=tenant_id)
        for user_id, calls in rows:
            calls = int(calls or 0)
            if not user_id:
                virtual_totals[_BUCKET_UNKNOWN_SYSTEM] = virtual_totals.get(_BUCKET_UNKNOWN_SYSTEM, 0) + calls
            elif str(user_id) in tenant_account_set:
                account_totals[str(user_id)] = account_totals.get(str(user_id), 0) + calls
            else:
                virtual_totals[_BUCKET_UNKNOWN] = virtual_totals.get(_BUCKET_UNKNOWN, 0) + calls

        member_departments = UsageStatisticService._account_departments(
            session, tenant_id=tenant_id, account_ids=set(account_totals.keys())
        )
        dept_totals = UsageStatisticService._department_calls(
            account_totals,
            member_departments=member_departments,
            virtual_buckets=set(),
        )
        for bucket, calls in virtual_totals.items():
            dept_totals[bucket] = dept_totals.get(bucket, 0) + calls

        real_ids = {d for d in dept_totals if d not in _VIRTUAL_BUCKET_NAMES}
        dept_info = UsageStatisticService._department_info_map(
            session, tenant_id=tenant_id, dept_ids=real_ids
        )
        data = UsageStatisticService._build_department_items(
            dept_totals, dept_info=dept_info, limit=limit
        )
        return {
            "dimension": "department",
            "total_calls": sum(account_totals.values()) + sum(virtual_totals.values()),
            "grouped_calls": sum(dept_totals.values()),
            "aggregation": "include_descendants",
            "data": data,
        }

    @staticmethod
    def kb_call_trend(
        session: Session,
        *,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        bucket: str = "day",
    ) -> list[dict[str, Any]]:
        """Knowledge-base call counts bucketed by time (daily or hourly)."""
        from models import Dataset

        tenant_ds = set(session.scalars(select(Dataset.id).where(Dataset.tenant_id == tenant_id)).all())
        if not tenant_ds:
            return []

        if bucket == "hour":
            # hour granularity uses PostgreSQL date_trunc (Dify default backend)
            expr = func.date_trunc("hour", DatasetQuery.created_at)
        else:
            expr = func.date(DatasetQuery.created_at)

        stmt = (
            select(expr.label("bucket"), func.count(DatasetQuery.id).label("total"))
            .where(
                DatasetQuery.dataset_id.in_(tenant_ds),
                DatasetQuery.created_at >= start_time,
                DatasetQuery.created_at <= end_time,
            )
            .group_by("bucket")
            .order_by("bucket")
        )
        rows = session.execute(stmt).all()
        return [{"bucket": str(r[0]), "calls": int(r[1] or 0)} for r in rows]

    @staticmethod
    def interface_call_counts(
        session: Session,
        *,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, int]:
        """Interface/event call volume from the audit log, grouped by log type."""
        stmt = (
            select(AuditLog.log_type, func.count(AuditLog.id).label("total"))
            .where(AuditLog.tenant_id == tenant_id)
            .group_by(AuditLog.log_type)
        )
        if start_time is not None:
            stmt = stmt.where(AuditLog.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.created_at <= end_time)

        counts: dict[str, int] = {}
        for r in session.execute(stmt).all():
            counts[(r[0].value if hasattr(r[0], "value") else r[0]) or "unknown"] = int(r[1] or 0)
        return counts

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)
