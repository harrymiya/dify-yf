"""Unit tests for the usage statistics console controller (requirement 4, D4).

Covers the ``dimension`` routing for the KB and interface "calls" endpoints,
default backward-compatible responses, permission gating and limit clamping.
Uses mock-session style (no real DB): the service layer is mocked and the
flask-restx / wrap / login decorators are neutralized BEFORE the module loads
(so ``@with_session`` etc. are bound to no-ops at class-definition time).
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
def usage_module():
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
        sys.modules.pop("controllers.console.usage_statistics", None)
        mod = importlib.import_module("controllers.console.usage_statistics")
        yield mod


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def owner_user():
    return SimpleNamespace(id="owner-1", current_role="owner")


@pytest.fixture
def editor_user():
    return SimpleNamespace(id="edit-1", current_role="normal")


def _patch_service(module, **methods):
    return patch.multiple(
        module.UsageStatisticService,
        kb_call_top=methods.get("kb_call_top", MagicMock(return_value=[])),
        kb_call_top_by_user=methods.get(
            "kb_call_top_by_user",
            MagicMock(return_value={"dimension": "user", "total_calls": 0, "data": []}),
        ),
        kb_call_top_by_department=methods.get(
            "kb_call_top_by_department",
            MagicMock(
                return_value={
                    "dimension": "department",
                    "total_calls": 0,
                    "grouped_calls": 0,
                    "aggregation": "include_descendants",
                    "data": [],
                }
            ),
        ),
        interface_call_counts=methods.get("interface_call_counts", MagicMock(return_value={})),
        interface_call_top_by_user=methods.get(
            "interface_call_top_by_user",
            MagicMock(return_value={"dimension": "user", "total_calls": 0, "data": []}),
        ),
        interface_call_top_by_department=methods.get(
            "interface_call_top_by_department",
            MagicMock(
                return_value={
                    "dimension": "department",
                    "total_calls": 0,
                    "grouped_calls": 0,
                    "aggregation": "include_descendants",
                    "data": [],
                }
            ),
        ),
    )


class _Calls:
    """Parameterised call helpers bound to the imported module."""

    def __init__(self, module, app):
        self.module = module
        self.app = app

    def _kb(self, session, current_user, query_string):
        with self.app.test_request_context(
            "/workspaces/current/statistics/knowledge-base/calls", query_string=query_string
        ):
            return self.module.KnowledgeBaseCallStatsApi().get(session, "tenant-1", current_user)

    def _interface(self, session, current_user, query_string):
        with self.app.test_request_context(
            "/workspaces/current/statistics/interfaces/calls", query_string=query_string
        ):
            return self.module.InterfaceCallStatsApi().get(session, "tenant-1", current_user)


def _call_kb(app, usage_module, session, current_user, query_string):
    return _Calls(usage_module, app)._kb(session, current_user, query_string)


def _call_interface(app, usage_module, session, current_user, query_string):
    return _Calls(usage_module, app)._interface(session, current_user, query_string)


class TestPermission:
    def test_kb_non_owner_admin_forbidden(self, app, usage_module, editor_user):
        with _patch_service(usage_module), pytest.raises(Forbidden):
            _call_kb(app, usage_module, MagicMock(), editor_user, {})

    def test_interface_non_owner_admin_forbidden(self, app, usage_module, editor_user):
        with _patch_service(usage_module), pytest.raises(Forbidden):
            _call_interface(app, usage_module, MagicMock(), editor_user, {})


class TestKbDimension:
    def test_default_dimension_backwards_compatible(self, app, usage_module, owner_user):
        kb_top = MagicMock(return_value=[{"dataset_id": "ds-1", "calls": 5}])
        with _patch_service(usage_module, kb_call_top=kb_top):
            body, status = _call_kb(app, usage_module, MagicMock(), owner_user, {})
        assert status == 200
        # default response keeps the legacy shape (no dimension key)
        assert body == {"days": 30, "total_calls": 5, "data": [{"dataset_id": "ds-1", "calls": 5}]}

    def test_user_dimension_routes(self, app, usage_module, owner_user):
        by_user = MagicMock(
            return_value={
                "dimension": "user",
                "total_calls": 3,
                "data": [{"id": "acc-1", "name": "Alice", "email": None, "is_virtual": False, "calls": 3}],
            }
        )
        with _patch_service(usage_module, kb_call_top_by_user=by_user):
            body, status = _call_kb(app, usage_module, MagicMock(), owner_user, {"dimension": "user"})
        assert status == 200
        assert body["days"] == 30
        assert body["dimension"] == "user"
        assert body["total_calls"] == 3
        by_user.assert_called_once()
        kwargs = by_user.call_args.kwargs
        assert kwargs["tenant_id"] == "tenant-1"
        assert kwargs["limit"] == 20

    def test_department_dimension_routes(self, app, usage_module, owner_user):
        by_dept = MagicMock(
            return_value={
                "dimension": "department",
                "total_calls": 3,
                "grouped_calls": 6,
                "aggregation": "include_descendants",
                "data": [],
            }
        )
        with _patch_service(usage_module, kb_call_top_by_department=by_dept):
            body, status = _call_kb(
                app, usage_module, MagicMock(), owner_user, {"dimension": "department", "limit": "50"}
            )
        assert status == 200
        assert body["dimension"] == "department"
        assert body["grouped_calls"] == 6
        assert body["aggregation"] == "include_descendants"
        assert by_dept.call_args.kwargs["limit"] == 50

    def test_invalid_dimension_rejected(self, app, usage_module, owner_user):
        with _patch_service(usage_module), pytest.raises(BadRequest):
            _call_kb(app, usage_module, MagicMock(), owner_user, {"dimension": "bogus"})

    def test_limit_clamped(self, app, usage_module, owner_user):
        by_user = MagicMock(return_value={"dimension": "user", "total_calls": 0, "data": []})
        with _patch_service(usage_module, kb_call_top_by_user=by_user):
            _call_kb(app, usage_module, MagicMock(), owner_user, {"dimension": "user", "limit": "500"})
        assert by_user.call_args.kwargs["limit"] == 100


class TestInterfaceDimension:
    def test_default_dimension_keeps_legacy_shape(self, app, usage_module, owner_user):
        counts = MagicMock(return_value={"retrieval": 5, "download": 2})
        with _patch_service(usage_module, interface_call_counts=counts):
            body, status = _call_interface(app, usage_module, MagicMock(), owner_user, {})
        assert status == 200
        assert body == {"days": 30, "total_calls": 7, "data": {"retrieval": 5, "download": 2}}

    def test_user_dimension_routes(self, app, usage_module, owner_user):
        by_user = MagicMock(return_value={"dimension": "user", "total_calls": 5, "data": []})
        with _patch_service(usage_module, interface_call_top_by_user=by_user):
            body, status = _call_interface(app, usage_module, MagicMock(), owner_user, {"dimension": "user"})
        assert status == 200
        assert body["dimension"] == "user"
        assert by_user.call_args.kwargs["tenant_id"] == "tenant-1"
        assert by_user.call_args.kwargs["limit"] == 20

    def test_department_dimension_routes(self, app, usage_module, owner_user):
        by_dept = MagicMock(
            return_value={
                "dimension": "department",
                "total_calls": 4,
                "grouped_calls": 8,
                "aggregation": "include_descendants",
                "data": [],
            }
        )
        with _patch_service(usage_module, interface_call_top_by_department=by_dept):
            body, status = _call_interface(app, usage_module, MagicMock(), owner_user, {"dimension": "department"})
        assert status == 200
        assert body["dimension"] == "department"
        assert body["aggregation"] == "include_descendants"
        assert by_dept.call_args.kwargs["limit"] == 20

    def test_invalid_dimension_rejected(self, app, usage_module, owner_user):
        with _patch_service(usage_module), pytest.raises(BadRequest):
            _call_interface(app, usage_module, MagicMock(), owner_user, {"dimension": "nope"})

    def test_limit_clamped(self, app, usage_module, owner_user):
        by_dept = MagicMock(
            return_value={
                "dimension": "department",
                "total_calls": 0,
                "grouped_calls": 0,
                "aggregation": "include_descendants",
                "data": [],
            }
        )
        with _patch_service(usage_module, interface_call_top_by_department=by_dept):
            _call_interface(app, usage_module, MagicMock(), owner_user, {"dimension": "department", "limit": "0"})
        assert by_dept.call_args.kwargs["limit"] == 1
