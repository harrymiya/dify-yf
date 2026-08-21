"""Unit tests for the audit log console controller (requirement 5, group B).

Covers department_id filtering, result enrichment (user_name / user_email /
department_ids / department_names), permission gating and the filtered ``total``
count. Uses mock-session style (no real DB): the service layer is mocked and the
flask-restx / wrap / login decorators are neutralized before the module loads.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest, Forbidden


def _identity(func, *args, **kwargs):  # noqa: ARG001
    """Neutralize a decorating wrapper by returning the decorated function."""
    return func


def _identity_session_decorator(write: bool = False):  # noqa: ARG001
    return _identity


@pytest.fixture
def audit_logs():
    """Import the controller module fresh with nulled decorators applied."""
    import importlib
    import sys

    with (
        patch("controllers.console.wraps.setup_required", _identity),
        patch("controllers.console.wraps.account_initialization_required", _identity),
        patch("controllers.console.wraps.with_current_user", lambda f: f),
        patch("controllers.console.wraps.with_current_tenant_id", lambda f: f),
        patch("libs.login.login_required", _identity),
        patch("controllers.common.session.with_session", _identity_session_decorator),
    ):
        sys.modules.pop("controllers.console.audit_logs", None)
        mod = importlib.import_module("controllers.console.audit_logs")
        yield mod


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def admin_user():
    return SimpleNamespace(id="admin-1", current_role="owner")


@pytest.fixture
def editor_user():
    return SimpleNamespace(id="edit-1", current_role="normal")


def _make_row(**overrides):
    base = {
        "id": "log-1",
        "user_id": "acct-1",
        "user_type": "account",
        "log_type": "retrieval",
        "action": "kb_retrieval",
        "status": "success",
        "resource_type": "dataset",
        "resource_id": "ds-1",
        "detail": None,
        "ip": "1.2.3.4",
        "request_id": "req-1",
        "trace_id": "trace-1",
        "created_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_service(mod, **methods):
    return patch.multiple(
        mod.AuditLogService,
        query=methods.get("query", MagicMock(return_value=[])),
        count=methods.get("count", MagicMock(return_value=0)),
        resolve_department_member_account_ids=methods.get(
            "resolve_department_member_account_ids", MagicMock(return_value=set())
        ),
        load_account_enrichment=methods.get(
            "load_account_enrichment", MagicMock(return_value=({}, {}))
        ),
    )


def _call_get(app, session, user, query_string, audit_log_list_api):
    with app.test_request_context("/workspaces/current/audit-logs", query_string=query_string):
        return audit_log_list_api().get(session, "tenant-1", user)


def test_uuid_validator(audit_logs):
    assert audit_logs._is_valid_uuid("d1f8b2a0-0000-0000-0000-000000000001")
    assert not audit_logs._is_valid_uuid("not-a-uuid")
    assert not audit_logs._is_valid_uuid("")


class TestPermission:
    def test_non_owner_admin_forbidden(self, app, editor_user, audit_logs):
        session = MagicMock()
        with _patch_service(audit_logs), pytest.raises(Forbidden):
            with app.test_request_context("/workspaces/current/audit-logs"):
                audit_logs.AuditLogListApi().get(session, "tenant-1", editor_user)


class TestDepartmentFilter:
    def test_valid_department_passes_resolved_accounts(self, app, admin_user, audit_logs):
        session = MagicMock()
        query_mock = MagicMock(return_value=[])
        count_mock = MagicMock(return_value=0)
        resolve_mock = MagicMock(return_value={"acct-1", "acct-2"})
        enrich_mock = MagicMock(return_value=({}, {}))
        with _patch_service(
            audit_logs,
            query=query_mock,
            count=count_mock,
            resolve_department_member_account_ids=resolve_mock,
            load_account_enrichment=enrich_mock,
        ):
            resp = _call_get(
                app,
                session,
                admin_user,
                {"department_id": "d1f8b2a0-0000-0000-0000-000000000001"},
                audit_logs.AuditLogListApi,
            )
        body, status = resp
        assert status == 200
        resolve_mock.assert_called_once_with(
            session,
            tenant_id="tenant-1",
            department_id="d1f8b2a0-0000-0000-0000-000000000001",
        )
        assert query_mock.call_args.kwargs["member_account_ids"] == {"acct-1", "acct-2"}
        assert count_mock.call_args.kwargs["member_account_ids"] == {"acct-1", "acct-2"}
        assert body["total"] == 0

    def test_invalid_department_id_rejected(self, app, admin_user, audit_logs):
        session = MagicMock()
        with _patch_service(audit_logs), pytest.raises(BadRequest):
            _call_get(app, session, admin_user, {"department_id": "not-a-uuid"}, audit_logs.AuditLogListApi)

    def test_empty_department_id_ignored(self, app, admin_user, audit_logs):
        session = MagicMock()
        query_mock = MagicMock(return_value=[])
        count_mock = MagicMock(return_value=0)
        resolve_mock = MagicMock(return_value=set())
        with _patch_service(
            audit_logs,
            query=query_mock,
            count=count_mock,
            resolve_department_member_account_ids=resolve_mock,
        ):
            resp = _call_get(app, session, admin_user, {"department_id": ""}, audit_logs.AuditLogListApi)
        body, status = resp
        assert status == 200
        resolve_mock.assert_not_called()
        assert query_mock.call_args.kwargs["member_account_ids"] is None

    def test_unknown_department_empty_set_filters(self, app, admin_user, audit_logs):
        session = MagicMock()
        query_mock = MagicMock(return_value=[])
        count_mock = MagicMock(return_value=0)
        resolve_mock = MagicMock(return_value=set())
        with _patch_service(
            audit_logs,
            query=query_mock,
            count=count_mock,
            resolve_department_member_account_ids=resolve_mock,
        ):
            resp = _call_get(
                app,
                session,
                admin_user,
                {"department_id": "d1f8b2a0-0000-0000-0000-000000000002"},
                audit_logs.AuditLogListApi,
            )
        body, status = resp
        assert status == 200
        assert query_mock.call_args.kwargs["member_account_ids"] == set()


class TestResultEnrichment:
    def test_rows_enriched_with_account_and_departments(self, app, admin_user, audit_logs):
        session = MagicMock()
        row = _make_row(id="log-1", user_id="acct-1")
        query_mock = MagicMock(return_value=[row])
        count_mock = MagicMock(return_value=1)
        accounts = {"acct-1": ("Alice", "alice@example.com")}
        departments = {"acct-1": [("dept-1", "研发"), ("dept-2", "后台")]}
        with _patch_service(
            audit_logs,
            query=query_mock,
            count=count_mock,
            load_account_enrichment=MagicMock(return_value=(accounts, departments)),
        ):
            resp = _call_get(app, session, admin_user, {}, audit_logs.AuditLogListApi)
        body, status = resp
        assert status == 200
        item = body["data"][0]
        assert item["user_name"] == "Alice"
        assert item["user_email"] == "alice@example.com"
        assert item["department_ids"] == ["dept-1", "dept-2"]
        assert item["department_names"] == ["研发", "后台"]
        assert item["id"] == "log-1"
        assert item["action"] == "kb_retrieval"

    def test_unknown_user_gives_null_and_empty_lists(self, app, admin_user, audit_logs):
        session = MagicMock()
        row = _make_row(id="log-2", user_id="missing")
        with _patch_service(
            audit_logs,
            query=MagicMock(return_value=[row]),
            count=MagicMock(return_value=1),
            load_account_enrichment=MagicMock(return_value=({}, {})),
        ):
            resp = _call_get(app, session, admin_user, {}, audit_logs.AuditLogListApi)
        body, status = resp
        item = body["data"][0]
        assert item["user_name"] is None
        assert item["user_email"] is None
        assert item["department_ids"] == []
        assert item["department_names"] == []
