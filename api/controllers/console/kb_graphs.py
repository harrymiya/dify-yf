"""Knowledge-graph endpoints - customization requirement 1 (tasks C4/C5).

Exposes build / read / retrieve / clear operations over the relational
knowledge graph of a dataset:

- ``POST   /datasets/<dataset_id>/kb-graph/build``   : run entity extraction over
  the dataset's completed segments (optionally one document) and persist the graph.
- ``GET    /datasets/<dataset_id>/kb-graph/entities``: list graph entities (paged).
- ``GET    /datasets/<dataset_id>/kb-graph/relations``: list graph edges (paged).
- ``GET    /datasets/<dataset_id>/kb-graph/stats``  : entity/relation counters.
- ``POST   /datasets/<dataset_id>/kb-graph/retrieve``: entity-based graph retrieval.
- ``DELETE /datasets/<dataset_id>/kb-graph``        : clear the dataset graph.

All routes are gated by ``@kb_permission_required`` (B3/B4). The retrieve route
also passes the interactive account down so ``GraphService.retrieve`` re-enforces
the B5 whitelist at the retrieval layer (C5 security baseline).
"""

import json
import logging
from uuid import UUID

from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.exceptions import NotFound

from controllers.common.kb_wraps import kb_permission_required
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
from core.rag.graph import GraphService
from core.rag.index_processor.constant.query_type import QueryType
from extensions.ext_database import db
from libs.login import login_required
from models import Account, Dataset, Document, KBPermissionAction, KBResourceType
from models.audit_log import AuditLogStatus, AuditLogType
from models.dataset import DatasetQuery, DocumentSegment
from models.enums import CreatorUserRole, DatasetQuerySource, SegmentStatus
from services.audit_log_service import AuditLogService
from services.dataset_service import DatasetService

logger = logging.getLogger(__name__)


class GraphBuildPayload(BaseModel):
    document_id: str | None = None


class GraphRetrievePayload(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)


register_schema_models(console_ns, GraphBuildPayload, GraphRetrievePayload)


def _get_dataset(dataset_id: UUID, tenant_id: str, session: Session) -> Dataset:
    dataset = DatasetService.get_dataset_for_tenant(str(dataset_id), tenant_id, session=session)
    if dataset is None:
        raise NotFound("Dataset not found.")
    return dataset


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph/build")
class KBGraphBuildApi(Resource):
    @console_ns.doc("build_kb_graph")
    @console_ns.doc(description="Build the knowledge graph from a dataset's completed segments")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_EDIT)
    @with_current_user
    @with_current_tenant_id
    @with_session
    @model_validate(GraphBuildPayload)
    def post(
        self,
        req_data: GraphBuildPayload,
        session: Session,
        current_tenant_id: str,
        current_user: Account,
        dataset_id: UUID,
    ):
        _get_dataset(dataset_id, current_tenant_id, session)
        document_id = req_data.document_id
        if document_id:
            document = session.scalar(
                select(Document).where(
                    Document.id == document_id,
                    Document.dataset_id == str(dataset_id),
                    Document.tenant_id == current_tenant_id,
                )
            )
            if document is None:
                raise NotFound("Document not found in this dataset.")
        segment_query = select(DocumentSegment).where(
            DocumentSegment.tenant_id == current_tenant_id,
            DocumentSegment.dataset_id == str(dataset_id),
            DocumentSegment.status == SegmentStatus.COMPLETED.value,
        )
        if document_id:
            segment_query = segment_query.where(DocumentSegment.document_id == document_id)
        segments = session.scalars(segment_query.order_by(DocumentSegment.position)).all()

        result = GraphService.build_graph(
            tenant_id=current_tenant_id,
            dataset_id=str(dataset_id),
            document_id=document_id,
            segments=segments,
            session=session,
        )
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.SYSTEM,
            action="kb_graph.build",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="dataset",
            resource_id=str(dataset_id),
            detail={
                "document_id": document_id,
                "entities_created": getattr(result, "entities_created", None),
                "relations_created": getattr(result, "relations_created", None),
                "segments_processed": getattr(result, "segments_processed", None),
            },
        )
        session.commit()
        return {"data": result.to_payload()}, 201


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph/entities")
class KBGraphEntityListApi(Resource):
    @console_ns.doc("list_kb_graph_entities")
    @console_ns.doc(description="List the knowledge-graph entities of a dataset")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_PREVIEW)
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, dataset_id: UUID):
        _get_dataset(dataset_id, current_tenant_id, session)
        keyword = request.args.get("keyword")
        try:
            offset = max(int(request.args.get("offset", "0")), 0)
        except ValueError:
            offset = 0
        try:
            limit = min(int(request.args.get("limit", "50")), 500)
        except ValueError:
            limit = 50
        rows = GraphService.list_entities(
            current_tenant_id, str(dataset_id), session, keyword=keyword, offset=offset, limit=limit
        )
        data = [
            {
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "description": e.description,
                "dataset_id": e.dataset_id,
                "document_id": e.document_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
        return {"data": data}, 200


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph/relations")
class KBGraphRelationListApi(Resource):
    @console_ns.doc("list_kb_graph_relations")
    @console_ns.doc(description="List the knowledge-graph relations of a dataset")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_PREVIEW)
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, dataset_id: UUID):
        _get_dataset(dataset_id, current_tenant_id, session)
        try:
            offset = max(int(request.args.get("offset", "0")), 0)
        except ValueError:
            offset = 0
        try:
            limit = min(int(request.args.get("limit", "200")), 500)
        except ValueError:
            limit = 200
        rows = GraphService.list_relations(current_tenant_id, str(dataset_id), session, offset=offset, limit=limit)
        data = [
            {
                "id": r.id,
                "source_entity_id": r.source_entity_id,
                "target_entity_id": r.target_entity_id,
                "relation_type": r.relation_type,
                "detail": r.detail,
            }
            for r in rows
        ]
        return {"data": data}, 200


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph/stats")
class KBGraphStatsApi(Resource):
    @console_ns.doc("kb_graph_stats")
    @console_ns.doc(description="Entity/relation counters of a dataset knowledge graph")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_PREVIEW)
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    def get(self, session: Session, current_tenant_id: str, current_user: Account, dataset_id: UUID):
        _get_dataset(dataset_id, current_tenant_id, session)
        return {"data": GraphService.graph_stats(current_tenant_id, str(dataset_id), session)}, 200


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph/retrieve")
class KBGraphRetrieveApi(Resource):
    @console_ns.doc("retrieve_kb_graph")
    @console_ns.doc(description="Entity-based knowledge-graph retrieval (with four-layer permission isolation)")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_RETRIEVAL_RECALL)
    @with_current_user
    @with_current_tenant_id
    @with_session(write=False)
    @model_validate(GraphRetrievePayload)
    def post(
        self,
        req_data: GraphRetrievePayload,
        session: Session,
        current_tenant_id: str,
        current_user: Account,
        dataset_id: UUID,
    ):
        _get_dataset(dataset_id, current_tenant_id, session)
        result = GraphService.retrieve(
            req_data.query,
            tenant_id=current_tenant_id,
            account=current_user,
            session=session,
            top_k=req_data.top_k,
            allowed_dataset_ids={str(dataset_id)},
        )
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.RETRIEVAL,
            action="kb_graph.retrieve",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="dataset",
            resource_id=str(dataset_id),
            detail={"query": req_data.query, "hits": len(getattr(result, "records", []) or [])},
        )
        KBGraphRetrieveApi._record_dataset_query(
            query=req_data.query,
            dataset_id=str(dataset_id),
            account_id=current_user.id,
        )
        session.commit()
        return {"data": result.to_payload()}, 200

    @staticmethod
    def _record_dataset_query(*, query: str, dataset_id: str, account_id: str) -> None:
        """Persist a DatasetQuery row for a graph retrieval in an independent session.

        The retrieve route runs on a read-only session, so instrumentation is
        committed in its own transaction. Failure to record must never break the
        retrieval response, hence the surrounding try/except.
        """
        try:
            content = json.dumps([{"content_type": QueryType.TEXT_QUERY.value, "content": query}])
            dataset_query = DatasetQuery(
                dataset_id=dataset_id,
                content=content,
                source=DatasetQuerySource.HIT_TESTING,
                source_app_id=None,
                created_by_role=CreatorUserRole.ACCOUNT,
                created_by=account_id,
            )
            with sessionmaker(bind=db.engine, expire_on_commit=False).begin() as independent_session:
                independent_session.add(dataset_query)
        except Exception:
            logger.warning(
                "Failed to persist kb-graph retrieval dataset query (dataset_id=%s)",
                dataset_id,
                exc_info=True,
            )


@console_ns.route("/datasets/<uuid:dataset_id>/kb-graph")
class KBGraphClearApi(Resource):
    @console_ns.doc("clear_kb_graph")
    @console_ns.doc(description="Clear the knowledge graph of a dataset")
    @setup_required
    @login_required
    @account_initialization_required
    @kb_permission_required(KBResourceType.DATASET, KBPermissionAction.DATASET_EDIT)
    @with_current_user
    @with_current_tenant_id
    @with_session
    def delete(self, session: Session, current_tenant_id: str, current_user: Account, dataset_id: UUID):
        _get_dataset(dataset_id, current_tenant_id, session)
        removed = GraphService.delete_dataset_graph(current_tenant_id, str(dataset_id), session)
        AuditLogService.record(
            tenant_id=current_tenant_id,
            log_type=AuditLogType.SYSTEM,
            action="kb_graph.clear",
            session=session,
            user_id=current_user.id,
            user_type="account",
            status=AuditLogStatus.SUCCESS,
            resource_type="dataset",
            resource_id=str(dataset_id),
            detail={"removed": removed},
        )
        session.commit()
        return {"result": "success", "removed": removed}, 200
