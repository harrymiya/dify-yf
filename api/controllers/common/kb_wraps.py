"""Decorator ``@kb_permission_required`` for the four-layer KB permission model.

Independent of the enterprise ``rbac_permission_required``: this gate evaluates
the community-edition ``kb_permission_grants`` table directly (default deny) and
never talks to the enterprise RBAC backend.

It resolves the current account/tenant itself (like ``rbac_permission_required``
does) so it can run above ``@with_current_user`` / ``@with_session`` in the
decorator stack and raises :class:`Forbidden` before the handler body runs.
"""

from collections.abc import Callable
from functools import wraps

from flask import request
from sqlalchemy import select
from werkzeug.exceptions import Forbidden, NotFound

from extensions.ext_database import db
from libs.login import current_account_with_tenant
from models import KBPermissionAction, KBResourceType
from services.kb_permission_service import KBPermissionService

__all__ = ["kb_permission_required", "extract_kb_resource_ids"]


def extract_kb_resource_ids(
    *, resource_type: KBResourceType, path_args: dict | None = None
) -> tuple[str | None, str | None]:
    """Extract ``(dataset_id, document_id)`` from the matched request path.

    ``document_id`` is only meaningful when ``resource_type`` is DOCUMENT.
    Source order: explicit ``path_args`` (used when the decorator is applied
    programmatically), then ``request.view_args``.
    """
    view_args = {**(request.view_args or {}), **(path_args or {})}

    dataset_id = view_args.get("dataset_id") or view_args.get("resource_id")
    document_id = view_args.get("document_id")
    if resource_type == KBResourceType.DOCUMENT and document_id is None and dataset_id is not None:
        # Document-scoped routes usually carry both dataset_id and document_id;
        # fall back to nothing if the document id is absent.
        document_id = None
    return (
        str(dataset_id) if dataset_id else None,
        str(document_id) if document_id else None,
    )


def _parent_dataset_of_document(document_id: str) -> str:
    """Resolve the owning dataset id of a document, raising NotFound."""
    from models import Document

    dataset_id = db.session.scalar(select(Document.dataset_id).where(Document.id == document_id))
    if not dataset_id:
        raise NotFound("document not found")
    return dataset_id


def kb_permission_required(
    resource_type: KBResourceType,
    action: KBPermissionAction,
    *,
    allow_owner: bool = True,
    message: str = "You do not have permission to access this resource.",
) -> Callable[[Callable], Callable]:
    """Verify the current user holds ``action`` on the requested KB resource.

    When enforcement is not configured (e.g. RBAC disabled in deployments that
    deliberately turn off knowledge permissions) the decorator still enforces
    the community four-layer model; there is no no-op escape hatch for security.
    """

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def decorated(*args, **kwargs):
            current_user, _ = current_account_with_tenant()
            dataset_id, document_id = extract_kb_resource_ids(resource_type=resource_type, path_args=kwargs)

            if resource_type == KBResourceType.DOCUMENT:
                doc_id = document_id or dataset_id  # document-scoped route
                if not doc_id:
                    raise Forbidden(message)
                parent_dataset_id = _parent_dataset_of_document(doc_id)
                KBPermissionService.require_permission(
                    current_user,
                    resource_type=KBResourceType.DATASET,
                    resource_id=parent_dataset_id,
                    action=KBPermissionAction.DATASET_USE.value,
                    session=db.session,
                    allow_owner=allow_owner,
                    message=message,
                )
                KBPermissionService.require_permission(
                    current_user,
                    resource_type=KBResourceType.DOCUMENT,
                    resource_id=doc_id,
                    action=action.value,
                    session=db.session,
                    allow_owner=allow_owner,
                    message=message,
                )
            else:
                if not dataset_id:
                    raise Forbidden(message)
                KBPermissionService.require_permission(
                    current_user,
                    resource_type=KBResourceType.DATASET,
                    resource_id=dataset_id,
                    action=action.value,
                    session=db.session,
                    allow_owner=allow_owner,
                    message=message,
                )
            return view(*args, **kwargs)

        return decorated

    return decorator
