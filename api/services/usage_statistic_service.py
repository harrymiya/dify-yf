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

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AuditLog, DatasetQuery

if TYPE_CHECKING:
    pass


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
        return datetime.now(timezone.utc)
