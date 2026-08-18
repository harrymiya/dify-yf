"""Unit tests for the four-layer KB permission service (requirement 3).

Covers default-deny, account/department(inheritance)/role grants, owner
short-circuit and the retrieval whitelist helper. Uses mock sessions and
accounts so no database is required.
"""

from unittest.mock import MagicMock

import pytest
from werkzeug.exceptions import Forbidden

from models.account import TenantAccountRole
from models.kb_permission import KBResourceType, KBSubjectType
from services.kb_permission_service import KBPermissionService


def _make_account(account_id: str = "acc-1", role: TenantAccountRole = TenantAccountRole.EDITOR, tenant_id: str = "tenant-1"):
    account = MagicMock()
    account.id = account_id
    account.current_tenant_id = tenant_id
    account.current_role = role
    return account


class TestDefaultDeny:
    def test_no_grants_means_deny(self):
        account = _make_account()
        session = MagicMock()
        # No grants match -> iterating the scalars result yields nothing.
        session.scalars.return_value = iter([])
        actions = KBPermissionService.resolve_effective_actions(
            account, resource_type=KBResourceType.DATASET, resource_id="ds-1", session=session
        )
        assert actions == set()
        assert (
            KBPermissionService.check_permission(
                account,
                resource_type=KBResourceType.DATASET,
                resource_id="ds-1",
                action="dataset_use",
                session=session,
            )
            is False
        )

    def test_require_permission_raises_forbidden(self):
        account = _make_account()
        session = MagicMock()
        session.scalars.return_value = iter([])
        with pytest.raises(Forbidden):
            KBPermissionService.require_permission(
                account,
                resource_type=KBResourceType.DATASET,
                resource_id="ds-1",
                action="dataset_use",
                session=session,
            )


class TestOwnerShortCircuit:
    def test_owner_always_allowed(self):
        account = _make_account(role=TenantAccountRole.OWNER)
        session = MagicMock()
        assert (
            KBPermissionService.check_permission(
                account,
                resource_type=KBResourceType.DATASET,
                resource_id="ds-1",
                action="dataset_delete",
                session=session,
            )
            is True
        )


class TestAccountGrant:
    def test_account_grant_allows_action(self):
        account = _make_account(account_id="acc-1")
        # The account holds no departments/roles; only its own account subject is matched.
        original = KBPermissionService.resolve_subject_ids
        KBPermissionService.resolve_subject_ids = MagicMock(
            return_value={
                KBSubjectType.ACCOUNT: {"acc-1"},
                KBSubjectType.DEPARTMENT: set(),
                KBSubjectType.ROLE: set(),
            }
        )
        try:
            session = MagicMock()
            # Each grant lookup returns one action (fresh iterator per call so the
            # earlier resolve_effective_actions call does not exhaust it).
            session.scalars.side_effect = lambda *a, **k: iter(["dataset_use"])
            actions = KBPermissionService.resolve_effective_actions(
                account, resource_type=KBResourceType.DATASET, resource_id="ds-1", session=session
            )
            assert actions == {"dataset_use"}
            assert (
                KBPermissionService.check_permission(
                    account,
                    resource_type=KBResourceType.DATASET,
                    resource_id="ds-1",
                    action="dataset_use",
                    session=session,
                )
                is True
            )
        finally:
            KBPermissionService.resolve_subject_ids = original


class TestDepartmentInheritance:
    def test_parent_department_grant_inherits(self):
        account = _make_account(account_id="acc-1")
        # The account belongs to dept-2 whose ancestor is dept-1; grant sits on dept-1.
        original_stats = (
            KBPermissionService.list_group_member_department_ids,
            KBPermissionService.expand_ancestor_departments,
            KBPermissionService.list_group_role_ids,
        )
        KBPermissionService.list_group_member_department_ids = MagicMock(return_value={"dept-2"})
        KBPermissionService.expand_ancestor_departments = MagicMock(return_value={"dept-2", "dept-1"})
        KBPermissionService.list_group_role_ids = MagicMock(return_value=set())
        try:
            session = MagicMock()
            session.scalars.side_effect = lambda *a, **k: iter(["dataset_use"])
            assert (
                KBPermissionService.check_permission(
                    account,
                    resource_type=KBResourceType.DATASET,
                    resource_id="ds-1",
                    action="dataset_use",
                    session=session,
                )
                is True
            )
        finally:
            (
                KBPermissionService.list_group_member_department_ids,
                KBPermissionService.expand_ancestor_departments,
                KBPermissionService.list_group_role_ids,
            ) = original_stats


class TestGrantedResourceIds:
    def test_whitelist_contains_granted_datasets(self):
        account = _make_account(account_id="acc-1")
        original = KBPermissionService.resolve_subject_ids
        KBPermissionService.resolve_subject_ids = MagicMock(
            return_value={
                KBSubjectType.ACCOUNT: {"acc-1"},
                KBSubjectType.DEPARTMENT: set(),
                KBSubjectType.ROLE: set(),
            }
        )
        try:
            session = MagicMock()
            session.scalars.return_value = iter(["ds-1", "ds-2"])
            result = KBPermissionService.granted_resource_ids(
                account, resource_type=KBResourceType.DATASET, action="dataset_use", session=session
            )
            assert result == {"ds-1", "ds-2"}
        finally:
            KBPermissionService.resolve_subject_ids = original

    def test_owner_whitelist_is_none(self):
        account = _make_account(role=TenantAccountRole.OWNER)
        session = MagicMock()
        assert (
            KBPermissionService.granted_resource_ids(
                account, resource_type=KBResourceType.DATASET, action="dataset_use", session=session
            )
            is None
        )


class TestDocumentDownloadPermission:
    """Regression for D2: the document-download endpoints enforce

    ``document_download`` (document-level) which also requires the owning
    dataset's ``dataset_use`` via the decorator. Here we verify the service
    resolution for the download action itself (default deny, grant allow).
    """

    def test_download_denied_without_grant(self):
        account = _make_account(account_id="acc-1")
        session = MagicMock()
        session.scalars.return_value = iter([])
        assert (
            KBPermissionService.check_permission(
                account,
                resource_type=KBResourceType.DOCUMENT,
                resource_id="doc-1",
                action="document_download",
                session=session,
            )
            is False
        )

    def test_download_allowed_with_grant(self):
        account = _make_account(account_id="acc-1")
        original = KBPermissionService.resolve_subject_ids
        KBPermissionService.resolve_subject_ids = MagicMock(
            return_value={
                KBSubjectType.ACCOUNT: {"acc-1"},
                KBSubjectType.DEPARTMENT: set(),
                KBSubjectType.ROLE: set(),
            }
        )
        try:
            session = MagicMock()
            session.scalars.return_value = iter(["document_download"])
            assert (
                KBPermissionService.check_permission(
                    account,
                    resource_type=KBResourceType.DOCUMENT,
                    resource_id="doc-1",
                    action="document_download",
                    session=session,
                )
                is True
            )
        finally:
            KBPermissionService.resolve_subject_ids = original

    def test_owner_download_always_allowed(self):
        account = _make_account(role=TenantAccountRole.OWNER)
        session = MagicMock()
        assert (
            KBPermissionService.check_permission(
                account,
                resource_type=KBResourceType.DOCUMENT,
                resource_id="doc-1",
                action="document_download",
                session=session,
            )
            is True
        )
