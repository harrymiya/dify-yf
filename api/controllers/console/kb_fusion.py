"""Knowledge fusion retrieval endpoints - unified assistant entry (requirement 1).

Exposes the multi-dataset fusion retrieval (`FusionService`) to the console as a
single unified entry point: a user submits one query and receives aggregated,
deduplicated results spanning **every** knowledge base they are permitted to
retrieve from (B5 permission whitelist enforced at the retrieval layer; owners
and admins are unrestricted within the workspace).
"""

from __future__ import annotations

from typing import Literal

from flask_restx import Resource
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from controllers.common.schema import register_schema_models
from controllers.common.session import with_session
from controllers.console import console_ns
from controllers.console.wraps import (
    account_initialization_required,
    model_validate,
    setup_required,
    with_current_tenant_id,
    with_current_user,
)
from core.rag.retrieval.fusion_service import FusionService, FusionStrategy
from libs.login import login_required
from models import Account, Dataset, KBPermissionAction, KBResourceType
from services.kb_permission_service import KBPermissionService


class FusionRetrievePayload(BaseModel):
    query: str = Field(min_length=1, max_length=250)
    top_k: int = Field(default=10, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    strategy: Literal["rrf", "max", "sum"] = Field(default=FusionStrategy.RRF)
    # None/empty = search every dataset the caller may retrieve from.
    dataset_ids: list[str] | None = Field(default=None)


register_schema_models(console_ns, FusionRetrievePayload)


@console_ns.route("/workspaces/current/kb-fusion/retrieve")
class KBFusionRetrieveApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    @model_validate(FusionRetrievePayload)
    def post(self, req_data: FusionRetrievePayload, session: Session, current_tenant_id: str, current_user: Account):
        # Resolve the datasets the caller may retrieve from. An owner/admin is
        # unrestricted (granted == None); other accounts get the grant whitelist.
        granted = KBPermissionService.granted_resource_ids(
            current_user,
            resource_type=KBResourceType.DATASET,
            action=KBPermissionAction.DATASET_RETRIEVAL_RECALL.value,
            session=session,
        )
        if granted is None:
            # Unrestricted: every dataset in this workspace.
            requested = req_data.dataset_ids
            if requested:
                allowed = set(requested)
            else:
                rows = session.scalars(
                    select(Dataset.id).where(Dataset.tenant_id == current_tenant_id)
                )
                allowed = {str(r) for r in rows}
        else:
            requested = set(req_data.dataset_ids) if req_data.dataset_ids else set()
            allowed = granted if not requested else granted & requested

        if not allowed:
            return {"query": req_data.query, "datasets": 0, "records": []}, 200

        result = FusionService.retrieve(
            query=req_data.query,
            dataset_ids=sorted(allowed),
            session=session,
            top_k=req_data.top_k,
            score_threshold=req_data.score_threshold,
            strategy=req_data.strategy,
            account=current_user,
        )
        return {
            "query": result.query,
            "datasets": len(allowed),
            "strategy": req_data.strategy,
            "records": result.to_payload()["records"],
        }, 200
