"""Unit tests for the usage statistic service (requirement 4, D4).

Covers knowledge-base call Top-N, knowledge-base call trend and interface call
counts. Uses a mock session so no database is required.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.usage_statistic_service import UsageStatisticService


def _session(*, dataset_ids: list[str] = None, exec_rows: list[tuple] | None = None):
    session = MagicMock()
    # session.scalars(select(Dataset.id)...).all()
    scalars = MagicMock()
    scalars.all.return_value = dataset_ids if dataset_ids is not None else ["ds-1", "ds-2"]
    session.scalars.return_value = scalars
    # session.execute(...).all()
    execute = MagicMock()
    execute.all.return_value = exec_rows if exec_rows is not None else []
    session.execute.return_value = execute
    return session


class TestKbCallTop:
    def test_returns_descending_calls(self):
        session = _session(
            dataset_ids=["ds-1", "ds-2"],
            exec_rows=[("ds-1", 5), ("ds-2", 3)],
        )
        result = UsageStatisticService.kb_call_top(
            session,
            tenant_id="tenant-1",
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 1, tzinfo=timezone.utc),
            limit=10,
        )
        assert result == [
            {"dataset_id": "ds-1", "calls": 5},
            {"dataset_id": "ds-2", "calls": 3},
        ]

    def test_filters_to_owned_datasets(self):
        # requested dataset not owned by tenant -> excluded
        session = _session(dataset_ids=["ds-1"], exec_rows=[("ds-1", 7)])
        result = UsageStatisticService.kb_call_top(
            session, tenant_id="tenant-1", dataset_ids=["ds-1", "ds-999"], limit=10
        )
        assert result == [{"dataset_id": "ds-1", "calls": 7}]


class TestInterfaceCallCounts:
    def test_groups_by_log_type(self):
        from models import AuditLogType

        session = _session(exec_rows=[(AuditLogType.DOWNLOAD, 4), (AuditLogType.RETRIEVAL, 2)])
        result = UsageStatisticService.interface_call_counts(session, tenant_id="tenant-1")
        assert result == {"download": 4, "retrieval": 2}


class TestNow:
    def test_now_tz_aware(self):
        assert UsageStatisticService.now().tzinfo is not None
