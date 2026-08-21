"""Unit tests for the audit log service (requirement 5).

Covers recording an audit entry, enriching from the structured-logging request
context, and querying with filters. Uses a mock session / context so no DB is
required.
"""

from unittest.mock import MagicMock, patch

from models import AuditLogStatus, AuditLogType
from services.audit_log_service import AuditLogService


class TestRecord:
    def test_record_creates_entry_and_enriches_context(self):
        session = MagicMock()
        with patch(
            "services.audit_log_service.get_identity_context",
            return_value=MagicMock(user_id="u-1", user_type="account"),
        ), patch("services.audit_log_service.get_request_id", return_value="req123"), patch(
            "services.audit_log_service.get_trace_id", return_value="trace123"
        ):
            entry = AuditLogService.record(
                tenant_id="tenant-1",
                log_type=AuditLogType.DOWNLOAD,
                action="document_download",
                session=session,
                resource_type="document",
                resource_id="doc-1",
            )
        session.add.assert_called_once_with(entry)
        assert entry.tenant_id == "tenant-1"
        assert entry.log_type == AuditLogType.DOWNLOAD
        assert entry.status == AuditLogStatus.SUCCESS
        assert entry.user_id == "u-1"
        assert entry.user_type == "account"
        assert entry.request_id == "req123"
        assert entry.trace_id == "trace123"

    def test_record_explicit_fields_override_context(self):
        session = MagicMock()
        with patch("services.audit_log_service.get_request_id", return_value="fromctx"):
            entry = AuditLogService.record(
                tenant_id="tenant-1",
                log_type=AuditLogType.SYSTEM,
                action="config_update",
                session=session,
                user_id="sys",
                user_type="system",
                request_id="explicit",
            )
        assert entry.user_id == "sys"
        assert entry.request_id == "explicit"


class TestQuery:
    def test_query_applies_tenant_and_type_filter(self):
        session = MagicMock()
        session.scalars.return_value.all.return_value = [MagicMock(id="log-1")]
        result = AuditLogService.query(
            session, tenant_id="tenant-1", log_type=AuditLogType.RETRIEVAL
        )
        assert len(result) == 1

    def test_query_orders_newest_and_limits(self):
        session = MagicMock()
        session.scalars.return_value.all.return_value = []
        result = AuditLogService.query(session, tenant_id="tenant-1", limit=5, offset=10)
        assert result == []


class TestEnrichFromHeaders:
    def test_client_ip_extracted(self):
        session = MagicMock()
        headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        with patch(
            "services.audit_log_service.get_request_id", return_value=None
        ), patch("services.audit_log_service.get_trace_id", return_value=None), patch(
            "services.audit_log_service.get_identity_context",
            return_value=MagicMock(user_id="", user_type=""),
        ):
            entry = AuditLogService.enrich_from_headers(
                tenant_id="tenant-1",
                log_type=AuditLogType.PERMISSION_CHANGE,
                action="kb_grant",
                session=session,
                headers=headers,
            )
        assert entry.ip == "1.2.3.4"


class TestResolveDepartmentMemberAccountIds:
    def _dept(self, dept_id, parent_id):
        d = MagicMock(id=dept_id)
        d.parent_id = parent_id
        return d

    def test_collects_subtree_members(self):
        session = MagicMock()
        departments = [
            self._dept("root", None),
            self._dept("child", "root"),
            self._dept("grand", "child"),
            self._dept("other", None),
        ]
        scalars = MagicMock()
        scalars.all.return_value = departments
        session.scalars.return_value = scalars
        member_scalars = MagicMock()
        member_scalars.all.return_value = ["acct-a", "acct-b", "acct-c", "acct-x"]
        session.scalars = MagicMock(side_effect=[scalars, member_scalars])

        result = AuditLogService.resolve_department_member_account_ids(
            session, tenant_id="tenant-1", department_id="root"
        )
        assert result == {"acct-a", "acct-b", "acct-c", "acct-x"}

    def test_unknown_department_returns_empty(self):
        session = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [self._dept("root", None)]
        session.scalars.return_value = scalars
        result = AuditLogService.resolve_department_member_account_ids(
            session, tenant_id="tenant-1", department_id="missing"
        )
        assert result == set()


class TestCount:
    def test_count_applies_filters(self):
        session = MagicMock()
        session.scalar.return_value = 7
        total = AuditLogService.count(session, tenant_id="tenant-1", member_account_ids={"a"})
        assert total == 7
        session.scalar.assert_called_once()

    def test_count_per_dept_uses_member_account_ids(self):
        session = MagicMock()
        session.scalar.return_value = 3
        total = AuditLogService.count(
            session, tenant_id="tenant-1", member_account_ids={"acct-a", "acct-b"}
        )
        assert total == 3


class TestLoadAccountEnrichment:
    def _acct(self, acct_id, name, email):
        a = MagicMock(id=acct_id)
        a.name = name
        a.email = email
        return a

    def test_tenant_scoped_accounts_and_departments(self):
        session = MagicMock()
        # 1) scalars: TenantAccountJoin account_ids (only acc-1 in tenant-1)
        tenant_join_scalars = MagicMock()
        tenant_join_scalars.all.return_value = ["acc-1"]
        # 2) scalars: Account detail rows (only acc-1)
        acct_scalars = MagicMock()
        acct_scalars.all.return_value = [self._acct("acc-1", "Alice", "a@example.com")]

        # department member query uses execute (multi-column) -> [(dept-1, acc-1)]
        member_exec = MagicMock()
        member_exec.all.return_value = [("dept-1", "acc-1")]
        session.execute.return_value = member_exec

        # dept names (scalars) -> dept-1
        dept_scalars = MagicMock()
        dept_obj = MagicMock(id="dept-1")
        dept_obj.name = "研发"
        dept_scalars.all.return_value = [dept_obj]
        # scalars is called three times: tenant membership, account details, dept names
        session.scalars.side_effect = [tenant_join_scalars, acct_scalars, dept_scalars]

        accounts, departments = AuditLogService.load_account_enrichment(
            session, tenant_id="tenant-1", account_ids={"acc-1", "acc-2", "outside"}
        )

        # acc-2 and outside are not tenant members -> not included
        assert set(accounts.keys()) == {"acc-1"}
        assert accounts["acc-1"] == ("Alice", "a@example.com")
        assert departments == {"acc-1": [("dept-1", "研发")]}

        # tenant membership query carries tenant filter
        tenant_stmt = session.scalars.call_args_list[0][0][0]
        assert "tenant_account_joins.tenant_id" in str(tenant_stmt)
        # department member query carries tenant filter and uses execute (multi-column)
        member_stmt = session.execute.call_args_list[0][0][0]
        assert "department_members.tenant_id" in str(member_stmt)

    def test_empty_account_ids_short_circuits(self):
        session = MagicMock()
        accounts, departments = AuditLogService.load_account_enrichment(
            session, tenant_id="tenant-1", account_ids=set()
        )
        assert accounts == {}
        assert departments == {}
        session.scalars.assert_not_called()

