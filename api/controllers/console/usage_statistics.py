"""Usage statistics endpoints - customization requirement 4 (D4).

Owner/admin-only dashboard endpoints exposing knowledge-base call volume,
interface call volume and time trends, aggregated by :class:`UsageStatisticService`.
"""

from datetime import UTC, datetime, timedelta

from flask import request
from flask_restx import Resource
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Forbidden

from controllers.common.session import with_session
from controllers.console import console_ns
from controllers.console.wraps import (
    account_initialization_required,
    setup_required,
    with_current_tenant_id,
    with_current_user,
)
from libs.login import login_required
from models import Account
from models.account import TenantAccountRole
from services.usage_statistic_service import UsageStatisticService


def _require_owner_or_admin(current_user: Account) -> None:
    if current_user.current_role not in (TenantAccountRole.OWNER, TenantAccountRole.ADMIN):
        raise Forbidden("Only the workspace owner or admin can read usage statistics.")


def _parse_range(days: int | None = None) -> tuple[datetime, datetime]:
    end = UsageStatisticService.now()
    start = (end - timedelta(days=days if days and days > 0 else 30)).astimezone(UTC)
    return start, end


_KB_DIMENSIONS = {"dataset", "user", "department"}
_INTERFACE_DIMENSIONS = {"type", "user", "department"}


def _parse_dimension(default: str, allowed: set[str]) -> str:
    dimension = request.args.get("dimension", default) or default
    if dimension not in allowed:
        raise BadRequest(f"Invalid dimension '{dimension}'.")
    return dimension


@console_ns.route("/workspaces/current/statistics/knowledge-base/calls")
class KnowledgeBaseCallStatsApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        _require_owner_or_admin(current_user)
        days = int(request.args.get("days", 30) or 30)
        limit = min(max(int(request.args.get("limit", 20) or 20), 1), 100)
        start, end = _parse_range(days)
        dimension = _parse_dimension("dataset", _KB_DIMENSIONS)
        if dimension == "dataset":
            top = UsageStatisticService.kb_call_top(
                session, tenant_id=current_tenant_id, start_time=start, end_time=end, limit=limit
            )
            total = sum(item["calls"] for item in top)
            return {"days": days, "total_calls": total, "data": top}, 200
        if dimension == "user":
            result = UsageStatisticService.kb_call_top_by_user(
                session, tenant_id=current_tenant_id, start_time=start, end_time=end, limit=limit
            )
            return {"days": days, **result}, 200
        result = UsageStatisticService.kb_call_top_by_department(
            session, tenant_id=current_tenant_id, start_time=start, end_time=end, limit=limit
        )
        return {"days": days, **result}, 200


@console_ns.route("/workspaces/current/statistics/knowledge-base/trend")
class KnowledgeBaseCallTrendApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        _require_owner_or_admin(current_user)
        days = int(request.args.get("days", 30) or 30)
        bucket = request.args.get("bucket", "day")
        start, end = _parse_range(days)
        trend = UsageStatisticService.kb_call_trend(
            session, tenant_id=current_tenant_id, start_time=start, end_time=end, bucket=bucket
        )
        return {"days": days, "bucket": bucket, "data": trend}, 200


@console_ns.route("/workspaces/current/statistics/interfaces/calls")
class InterfaceCallStatsApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account):
        _require_owner_or_admin(current_user)
        days = int(request.args.get("days", 30) or 30)
        limit = min(max(int(request.args.get("limit", 20) or 20), 1), 100)
        start, end = _parse_range(days)
        dimension = _parse_dimension("type", _INTERFACE_DIMENSIONS)
        if dimension == "type":
            counts = UsageStatisticService.interface_call_counts(
                session, tenant_id=current_tenant_id, start_time=start, end_time=end
            )
            return {"days": days, "total_calls": sum(counts.values()), "data": counts}, 200
        if dimension == "user":
            result = UsageStatisticService.interface_call_top_by_user(
                session, tenant_id=current_tenant_id, start_time=start, end_time=end, limit=limit
            )
            return {"days": days, **result}, 200
        result = UsageStatisticService.interface_call_top_by_department(
            session, tenant_id=current_tenant_id, start_time=start, end_time=end, limit=limit
        )
        return {"days": days, **result}, 200
