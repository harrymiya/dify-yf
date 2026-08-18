"""Unit tests for the audit log service (requirement 5).

Covers recording an audit entry, enriching from the structured-logging request
context, and querying with filters. Uses a mock session / context so no DB is
required.
"""

from unittest.mock import MagicMock, patch

from models import AuditLog, AuditLogStatus, AuditLogType
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
