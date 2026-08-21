"""Unit tests for the usage statistic service (requirement 4, D4).

Covers knowledge-base call Top-N, knowledge-base call trend, interface call
counts and the per-user / per-department aggregations. Uses a mock session so no
database is required.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from services.usage_statistic_service import UsageStatisticService


def _session(*, dataset_ids: list[str] | None = None, exec_rows: list[tuple] | None = None):
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
            start_time=datetime(2026, 1, 1, tzinfo=UTC),
            end_time=datetime(2026, 2, 1, tzinfo=UTC),
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


# --------------------------------------------------------------------- #
# Per-user / per-department KB aggregation.
# --------------------------------------------------------------------- #

ACCOUNT = "account"  # CreatorUserRole.ACCOUNT.value
END_USER = "end_user"  # CreatorUserRole.END_USER.value

TENANT_IDS = {"acc-1", "acc-2"}
APP_MAP = {"app-1": "acc-1"}  # app-1 owned by acc-1 (tenant)
ACCOUNT_MAP = {
    "acc-1": {"name": "Alice", "email": "a@example.com"},
    "acc-2": {"name": "Bob", "email": "b@example.com"},
}


class TestKbByUser:
    def test_account_direct_attribution(self):
        rows = [(ACCOUNT, "acc-1", None), (ACCOUNT, "acc-1", None), (ACCOUNT, "acc-2", None)]
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map={}, tenant_account_set=TENANT_IDS
        )
        assert totals == {"acc-1": 2, "acc-2": 1}

    def test_end_user_attributed_to_app_owner(self):
        rows = [(END_USER, "eu-1", "app-1")]
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map=APP_MAP, tenant_account_set=TENANT_IDS
        )
        assert totals == {"acc-1": 1}

    def test_external_bucket_when_app_missing(self):
        rows = [(END_USER, "eu-1", "app-missing")]
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map=APP_MAP, tenant_account_set=TENANT_IDS
        )
        assert totals == {"__external_api__": 1}

    def test_unknown_bucket_for_out_of_tenant_account(self):
        rows = [(ACCOUNT, "outside-account", None)]
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map={}, tenant_account_set=TENANT_IDS
        )
        assert totals == {"__unknown__": 1}

    def test_app_owner_out_of_tenant_unknowns(self):
        # app belongs to tenant but owner account is not in tenant -> unknown
        rows = [(END_USER, "eu-1", "app-2")]
        totals = UsageStatisticService._aggregate_kb_by_account(
            rows, app_map={"app-2": "outside-account"}, tenant_account_set=TENANT_IDS
        )
        assert totals == {"__unknown__": 1}

    def test_build_user_items_sorted_and_virtual_last(self):
        totals = {"acc-2": 3, "__unknown__": 1, "acc-1": 3}
        items = UsageStatisticService._build_user_items(totals, account_map=ACCOUNT_MAP, limit=10)
        assert [i["id"] for i in items] == ["acc-1", "acc-2", "__unknown__"]
        assert items[0] == {
            "id": "acc-1",
            "name": "Alice",
            "email": "a@example.com",
            "is_virtual": False,
            "calls": 3,
        }
        assert items[-1]["is_virtual"] is True

    def test_limit_truncates(self):
        totals = {"acc-1": 5, "acc-2": 3}
        items = UsageStatisticService._build_user_items(totals, account_map=ACCOUNT_MAP, limit=1)
        assert len(items) == 1
        assert items[0]["id"] == "acc-1"

    def test_public_method_orchestrates_query(self):
        # patch all fetch helpers; verify output shape + rows used.
        session = _session()
        with (
            patch.object(
                UsageStatisticService,
                "_tenant_dataset_id_set",
                return_value={"ds-1"},
            ) as ds,
            patch.object(
                UsageStatisticService,
                "_fetch_kb_query_rows",
                return_value=[(ACCOUNT, "acc-1", None), (ACCOUNT, "acc-2", None)],
            ) as fetch,
            patch.object(
                UsageStatisticService,
                "_apps_created_by",
                return_value={},
            ),
            patch.object(
                UsageStatisticService,
                "_accounts_name_email",
                return_value=ACCOUNT_MAP,
            ),
            patch.object(
                UsageStatisticService,
                "_tenant_account_ids",
                return_value=TENANT_IDS,
            ),
        ):
            result = UsageStatisticService.kb_call_top_by_user(
                session,
                tenant_id="tenant-1",
                dataset_ids=["ds-1", "ds-other"],
                start_time=datetime(2026, 1, 1, tzinfo=UTC),
                end_time=datetime(2026, 2, 1, tzinfo=UTC),
                limit=20,
            )
        ds.assert_called_once()
        args = fetch.call_args
        assert args.kwargs["dataset_ids"] == {"ds-1"}
        assert args.kwargs["start_time"] is not None
        assert args.kwargs["end_time"] is not None
        assert result["dimension"] == "user"
        assert result["total_calls"] == 2
        assert {i["id"] for i in result["data"]} == {"acc-1", "acc-2"}


class TestKbByDepartment:
    def test_department_calls_fan_out_to_ancestors(self):
        totals = {"acc-1": 5}
        member = {"acc-1": {"dept-child", "dept-parent"}}
        result = UsageStatisticService._department_calls(
            totals,
            member_departments=member,
            virtual_buckets={"__external_api__", "__unknown__"},
        )
        assert result == {"dept-child": 5, "dept-parent": 5}

    def test_grouped_calls_gte_total(self):
        result = UsageStatisticService._department_payload(
            {"acc-1": 5},
            session=MagicMock(),
            tenant_id="tenant-1",
            virtual_buckets={"__external_api__", "__unknown__"},
            limit=20,
        )
        assert result["grouped_calls"] >= result["total_calls"]

    def test_unassigned_when_account_has_no_department(self):
        totals = {"acc-1": 4}
        member = {}
        result = UsageStatisticService._department_calls(
            totals, member_departments=member, virtual_buckets={"__external_api__", "__unknown__"}
        )
        assert result == {"__unassigned__": 4}

    def test_external_bucket_passed_through(self):
        totals = {"__external_api__": 2, "acc-1": 3}
        member = {"acc-1": {"dept-1"}}
        result = UsageStatisticService._department_calls(
            totals, member_departments=member, virtual_buckets={"__external_api__", "__unknown__"}
        )
        assert result["__external_api__"] == 2
        assert result["dept-1"] == 3

    def test_build_department_items_shape(self):
        dept_totals = {"dept-1": 9, "__unassigned__": 2}
        dept_info = {"dept-1": {"name": "研发", "parent_id": None}}
        items = UsageStatisticService._build_department_items(
            dept_totals, dept_info=dept_info, limit=10
        )
        first = items[0]
        assert first == {
            "id": "dept-1",
            "name": "研发",
            "parent_id": None,
            "is_virtual": False,
            "calls": 9,
        }
        assert items[-1]["id"] == "__unassigned__"
        assert items[-1]["is_virtual"] is True

    def test_public_method_returns_aggregation_flag(self):
        session = _session()
        member = {"acc-1": {"root"}}
        with (
            patch.object(UsageStatisticService, "_tenant_dataset_id_set", return_value={"ds-1"}),
            patch.object(
                UsageStatisticService,
                "_fetch_kb_query_rows",
                return_value=[(ACCOUNT, "acc-1", None)],
            ),
            patch.object(UsageStatisticService, "_apps_created_by", return_value={}),
            patch.object(
                UsageStatisticService,
                "_accounts_name_email",
                return_value=ACCOUNT_MAP,
            ),
            patch.object(UsageStatisticService, "_tenant_account_ids", return_value=TENANT_IDS),
            patch.object(
                UsageStatisticService,
                "_account_departments",
                return_value=member,
            ),
            patch.object(
                UsageStatisticService,
                "_department_info_map",
                return_value={"root": {"name": "全公司", "parent_id": None}},
            ),
        ):
            result = UsageStatisticService.kb_call_top_by_department(
                session, tenant_id="tenant-1", limit=20
            )
        assert result["dimension"] == "department"
        assert result["aggregation"] == "include_descendants"
        assert result["total_calls"] == 1
        assert result["data"][0]["id"] == "root"


class TestInterfaceByUser:
    def _run(self, rows, tenant_ids=TENANT_IDS, account_map=ACCOUNT_MAP):
        session = _session(exec_rows=rows)
        with (
            patch.object(UsageStatisticService, "_tenant_account_ids", return_value=set(tenant_ids)),
            patch.object(UsageStatisticService, "_accounts_name_email", return_value=account_map),
        ):
            return UsageStatisticService.interface_call_top_by_user(
                session, tenant_id="tenant-1", limit=20
            )

    def test_empty_user_id_goes_to_unknown_system(self):
        result = self._run([(None, 3)])
        assert result["data"] == [
            {
                "id": "__unknown_system__",
                "name": "未知 / 系统",
                "email": None,
                "is_virtual": True,
                "calls": 3,
            }
        ]
        assert result["total_calls"] == 3

    def test_out_of_tenant_user_goes_to_unknown(self):
        result = self._run([("outside", 2)])
        assert result["data"][0]["id"] == "__unknown__"
        assert result["data"][0]["is_virtual"] is True

    def test_unknown_buckets_merged_for_multiple_out_of_tenant_users(self):
        result = self._run([("outside-1", 2), ("outside-2", 3)])
        assert result["data"] == [
            {
                "id": "__unknown__",
                "name": "未知账号",
                "email": None,
                "is_virtual": True,
                "calls": 5,
            }
        ]
        assert result["total_calls"] == 5

    def test_virtual_buckets_last_even_when_higher_calls(self):
        # __unknown__ has the most calls but must still be sorted after real users.
        result = self._run([("acc-1", 2), ("outside", 50)])
        ids = [i["id"] for i in result["data"]]
        assert ids == ["acc-1", "__unknown__"]
        assert result["data"][-1]["calls"] == 50

    def test_tenant_user_with_name_email(self):
        result = self._run([("acc-1", 7)])
        assert result["data"][0] == {
            "id": "acc-1",
            "name": "Alice",
            "email": "a@example.com",
            "is_virtual": False,
            "calls": 7,
        }


class TestInterfaceByDepartment:
    def test_department_aggregation(self):
        session = _session(exec_rows=[("acc-1", 4), (None, 2)])
        with (
            patch.object(UsageStatisticService, "_tenant_account_ids", return_value=TENANT_IDS),
            patch.object(
                UsageStatisticService,
                "_accounts_name_email",
                return_value=ACCOUNT_MAP,
            ),
            patch.object(
                UsageStatisticService,
                "_account_departments",
                return_value={"acc-1": {"dept-1", "root"}},
            ),
            patch.object(
                UsageStatisticService,
                "_department_info_map",
                return_value={"dept-1": {"name": "组", "parent_id": "root"}, "root": {"name": "根", "parent_id": None}},
            ),
        ):
            result = UsageStatisticService.interface_call_top_by_department(
                session, tenant_id="tenant-1", limit=20
            )
        by_id = {i["id"]: i for i in result["data"]}
        assert by_id["dept-1"]["calls"] == 4
        assert by_id["root"]["calls"] == 4
        assert by_id["__unknown_system__"]["calls"] == 2
        assert result["dimension"] == "department"
        assert result["aggregation"] == "include_descendants"


class TestAccountDepartmentsTenantScoped:
    def test_memberships_filtered_by_tenant(self):
        """Cross-tenant department_members rows must not be attributed to the current tenant."""
        session = MagicMock()

        def _execute_side_effect(stmt):
            clause = str(stmt)
            if "department_members" in clause:
                exec_ = MagicMock()
                # acc-1 is a member of dept-1 in this tenant; acc-1 also belongs to
                # another tenant's dept-999 (must be excluded by tenant_id filter).
                exec_.all.return_value = [("acc-1", "dept-1")]
                return exec_
            # departments (parent chain) query
            exec_ = MagicMock()
            exec_.all.return_value = [("dept-1", None), ("dept-2", "dept-1")]
            return exec_

        session.execute.side_effect = _execute_side_effect

        result = UsageStatisticService._account_departments(
            session, tenant_id="tenant-1", account_ids={"acc-1"}
        )
        # Only dept-1 (this-tenant) is included; dept-999 from the other tenant is excluded.
        assert result == {"acc-1": {"dept-1"}}
        # The member query must carry the tenant filter.
        member_stmt = session.execute.call_args_list[0][0][0]
        assert "department_members.tenant_id" in str(member_stmt)

    def test_no_memberships_returns_empty(self):
        session = MagicMock()
        session.execute.return_value.all.return_value = []
        result = UsageStatisticService._account_departments(
            session, tenant_id="tenant-1", account_ids={"acc-1"}
        )
        assert result == {}

    def test_empty_account_ids_short_circuits(self):
        session = MagicMock()
        result = UsageStatisticService._account_departments(
            session, tenant_id="tenant-1", account_ids=set()
        )
        assert result == {}
        session.execute.assert_not_called()

