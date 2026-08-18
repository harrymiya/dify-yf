import sqlalchemy as sa
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class KBSubjectType(StrEnum):
    """Type of the authorization subject in a grant."""

    ACCOUNT = "account"
    DEPARTMENT = "department"
    ROLE = "role"


class KBResourceType(StrEnum):
    """Type of the protected resource in a grant."""

    DATASET = "dataset"
    DOCUMENT = "document"


class KBPermissionAction(StrEnum):
    """Granular operations granted on a knowledge resource.

    Dataset-level actions mirror the existing ``RBACPermission.DATASET_*``
    points; document-level actions extend them to single documents.
    """

    # dataset-level
    DATASET_PREVIEW = "dataset_preview"
    DATASET_READONLY = "dataset_readonly"
    DATASET_EDIT = "dataset_edit"
    DATASET_RETRIEVAL_RECALL = "dataset_retrieval_recall"
    DATASET_USE = "dataset_use"
    DATASET_DOCUMENT_DOWNLOAD = "dataset_document_download"
    DATASET_DELETE_FILE = "dataset_delete_file"
    DATASET_DELETE = "dataset_delete"
    DATASET_ACCESS_CONFIG = "dataset_access_config"
    DATASET_API_KEY_MANAGE = "dataset_api_key_manage"

    # document-level
    DOCUMENT_READ = "document_read"
    DOCUMENT_RETRIEVAL = "document_retrieval"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_EDIT = "document_edit"
    DOCUMENT_DELETE = "document_delete"


class KBPermissionGrant(TypeBase):
    """Core four-layer authorization grant.

    A row grants ``action`` on ``resource`` (a dataset or a document) to a
    *subject* (an account, a department - including its ancestor chain when
    resolved - or a role).

    Default policy is **deny**: a user only gets access when at least one
    matching grant resolves for them.
    """

    __tablename__ = "kb_permission_grants"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="kb_permission_grant_pkey"),
        Index("idx_kb_grants_tenant_resource", "tenant_id", "resource_type", "resource_id"),
        Index("idx_kb_grants_subject", "subject_type", "subject_id"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    subject_type: Mapped[KBSubjectType] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    resource_type: Mapped[KBResourceType] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    action: Mapped[KBPermissionAction] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, init=False
    )
