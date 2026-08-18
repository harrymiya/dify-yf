"""GraphService - knowledge-graph build and retrieval (tasks C4/C5).

A lightweight relational-table knowledge graph (per the plan's §8 decision to
prototype with relational tables before adopting a graph database). Entities and
typed relations are tenant/dataset-scoped so they can be isolated by the same
four-layer KB permission whitelist used elsewhere.

C4 (build + retrieval):

- ``build_graph``  : run the entity extractor over document segments and upsert
  entities/relations into ``graph_entities`` / ``graph_relations``.
- ``retrieve``     : extract the query's entities, match them against stored
  entities, traverse typed relations (BFS) and return the surrounding sub-graph.

C5 (permission isolation):

- ``retrieve`` accepts the interactive ``account`` and intersects the requested
  dataset scope with ``KBPermissionService.granted_resource_ids`` (the same B5
  whitelist used by ``RetrievalService`` / ``FusionService``). An owner resolves
  to ``None`` (unrestricted); default-deny users only reach their granted
  datasets. Runtime app/workflow callers pass no account and are unaffected.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from core.rag.graph.entities import (
    GraphBuildResult,
    GraphEntityRecord,
    GraphRelationRecord,
    GraphRetrievalResult,
)
from models import GraphEntity, GraphRelation, KBPermissionAction, KBResourceType

if TYPE_CHECKING:
    from models import Account

logger = logging.getLogger(__name__)

#: default max BFS depth for relation traversal.
DEFAULT_MAX_DEPTH = 2
#: hard cap on relations collected during a single retrieval (blast radius guard).
MAX_RELATIONS_PER_RETRIEVAL = 200
#: per-name candidate cap while matching query entities.
MAX_CANDIDATES_PER_NAME = 20

__all__ = ["GraphService"]


class GraphService:
    """Build, query and isolate the relational knowledge graph."""

    # ------------------------------------------------------------------ #
    # Build (C4)
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_graph(
        tenant_id: str,
        dataset_id: str,
        document_id: str | None,
        segments: Iterable[Any],
        session: Session,
        extractor: Any | None = None,
    ) -> GraphBuildResult:
        """Extract entities/relations from ``segments`` and persist them.

        ``segments`` items may be ``DocumentSegment`` ORM objects or dicts with
        at least a ``content`` (and optionally ``document_id``) key. When
        ``document_id`` is provided the whole build is scoped to that document
        (the caller filters the segments accordingly).

        Extraction is best-effort: a failing segment is skipped and logged
        instead of aborting the whole build.
        """
        from core.rag.graph.entity_extractor import GraphEntityExtractor

        extractor = extractor or GraphEntityExtractor.extract
        result = GraphBuildResult()

        # (normalized name, entity_type) -> entity id, cached per build run.
        entity_cache: dict[tuple[str, str | None], str] = {}

        for segment in segments:
            content = GraphService._segment_content(segment)
            doc_id = GraphService._segment_document_id(segment) or document_id
            if not content or not content.strip():
                result.segments_skipped += 1
                continue
            try:
                entities, relations = extractor(content, tenant_id=tenant_id, session=session)
            except Exception:
                logger.warning("graph build: segment extraction failed", exc_info=True)
                result.segments_skipped += 1
                continue

            result.segments_processed += 1

            entity_ids: dict[str, str] = {}
            for ent in entities:
                name = GraphService._clean_name(ent.get("name"))
                if not name:
                    continue
                entity_type = GraphService._clean_type(ent.get("type"))
                key = (name.lower(), entity_type)
                if key in entity_cache:
                    entity_ids[name.lower()] = entity_cache[key]
                    result.entities_matched += 1
                    continue
                entity, created = GraphService._get_or_create_entity(
                    tenant_id=tenant_id,
                    dataset_id=dataset_id,
                    document_id=doc_id,
                    name=name,
                    entity_type=entity_type,
                    description=GraphService._clean_text(ent.get("description")),
                    session=session,
                )
                entity_cache[key] = entity.id
                entity_ids[name.lower()] = entity.id
                if created:
                    result.entities_created += 1
                else:
                    result.entities_matched += 1

            for rel in relations:
                source_name = GraphService._clean_name(rel.get("source"))
                target_name = GraphService._clean_name(rel.get("target"))
                if not source_name or not target_name:
                    continue
                # relations may reference entities the current segment did not list;
                # upsert them as orphan-safe nodes too.
                for name in (source_name, target_name):
                    if name.lower() not in entity_ids:
                        entity, created = GraphService._get_or_create_entity(
                            tenant_id=tenant_id,
                            dataset_id=dataset_id,
                            document_id=doc_id,
                            name=name,
                            entity_type=None,
                            description=None,
                            session=session,
                        )
                        entity_cache[(name.lower(), None)] = entity.id
                        entity_ids[name.lower()] = entity.id
                        if created:
                            result.entities_created += 1
                        else:
                            result.entities_matched += 1
                relation_type = GraphService._clean_type(rel.get("type")) or "related_to"
                if GraphService._relation_exists(
                    tenant_id=tenant_id,
                    source_entity_id=entity_ids[source_name.lower()],
                    target_entity_id=entity_ids[target_name.lower()],
                    relation_type=relation_type,
                    session=session,
                ):
                    continue
                session.add(
                    GraphRelation(
                        tenant_id=tenant_id,
                        source_entity_id=entity_ids[source_name.lower()],
                        target_entity_id=entity_ids[target_name.lower()],
                        relation_type=relation_type,
                        detail=rel.get("detail") or {},
                    )
                )
                result.relations_created += 1

        return result

    # ------------------------------------------------------------------ #
    # Retrieval (C4) + permission isolation (C5)
    # ------------------------------------------------------------------ #
    @staticmethod
    def retrieve(
        query: str,
        *,
        tenant_id: str,
        account: Account | None = None,
        session: Session,
        top_k: int = 10,
        allowed_dataset_ids: set[str] | None = None,
        extractor: Any | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> GraphRetrievalResult:
        """Return the sub-graph around the query's entities.

        C5: when ``account`` is provided the effective dataset scope is the
        intersection of the requested ``allowed_dataset_ids`` with the caller's
        ``dataset_retrieval_recall`` whitelist (B5). A tenant owner resolves to
        ``None`` (unrestricted within the tenant).
        """
        from core.rag.graph.entity_extractor import GraphEntityExtractor

        extractor = extractor or GraphEntityExtractor.extract
        allowed = GraphService._resolve_scope(account=account, requested=allowed_dataset_ids, session=session)
        if allowed == set():
            return GraphRetrievalResult(query=query)

        try:
            entities, _ = extractor(query, tenant_id=tenant_id, session=session, for_query=True)
        except Exception:
            logger.warning("graph retrieve: query extraction failed", exc_info=True)
            entities = []

        names = [GraphService._clean_name(e.get("name")) for e in entities]
        names = [n for n in names if n]

        matches = GraphService._match_entities(
            tenant_id=tenant_id, names=names, allowed_dataset_ids=allowed, session=session
        )
        matched_entities, scores = matches

        records: dict[str, GraphEntityRecord] = {}
        relations_out: dict[str, GraphRelationRecord] = {}

        for entity in matched_entities:
            records[entity.id] = GraphService._to_record(entity, score=scores[entity.id])

        if matched_entities:
            GraphService._traverse(
                start_ids={e.id for e in matched_entities},
                tenant_id=tenant_id,
                session=session,
                records=records,
                relations_out=relations_out,
                max_depth=max_depth,
            )

        ranked = sorted(records.values(), key=lambda r: r.score, reverse=True)[:top_k]
        relations = sorted(relations_out.values(), key=lambda r: r.id)
        return GraphRetrievalResult(query=query, records=ranked, relations=relations)

    # ------------------------------------------------------------------ #
    # Read helpers (controller-facing)
    # ------------------------------------------------------------------ #
    @staticmethod
    def list_entities(
        tenant_id: str,
        dataset_id: str,
        session: Session,
        *,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[GraphEntity]:
        stmt = select(GraphEntity).where(GraphEntity.tenant_id == tenant_id, GraphEntity.dataset_id == dataset_id)
        if keyword:
            stmt = stmt.where(GraphEntity.name.ilike(f"%{keyword}%"))
        stmt = stmt.order_by(GraphEntity.name).offset(offset).limit(limit)
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_relations(
        tenant_id: str,
        dataset_id: str,
        session: Session,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> list[GraphRelation]:
        stmt = (
            select(GraphRelation)
            .join(GraphEntity, GraphRelation.source_entity_id == GraphEntity.id)
            .where(
                GraphRelation.tenant_id == tenant_id,
                GraphEntity.dataset_id == dataset_id,
            )
            .order_by(GraphRelation.created_at)
            .offset(offset)
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def graph_stats(tenant_id: str, dataset_id: str, session: Session) -> dict[str, int]:
        entity_count = (
            session.scalar(
                select(func.count(GraphEntity.id)).where(
                    GraphEntity.tenant_id == tenant_id, GraphEntity.dataset_id == dataset_id
                )
            )
            or 0
        )
        relation_count = (
            session.scalar(
                select(func.count(GraphRelation.id))
                .join(GraphEntity, GraphRelation.source_entity_id == GraphEntity.id)
                .where(GraphRelation.tenant_id == tenant_id, GraphEntity.dataset_id == dataset_id)
            )
            or 0
        )
        return {"entities": int(entity_count), "relations": int(relation_count)}

    @staticmethod
    def delete_dataset_graph(tenant_id: str, dataset_id: str, session: Session) -> int:
        """Delete the graph sub-graph of a dataset (on dataset/document delete)."""
        entity_ids = list(
            session.scalars(
                select(GraphEntity.id).where(GraphEntity.tenant_id == tenant_id, GraphEntity.dataset_id == dataset_id)
            )
        )
        removed_relations = session.execute(
            delete(GraphRelation).where(
                GraphRelation.tenant_id == tenant_id,
                or_(
                    GraphRelation.source_entity_id.in_(entity_ids),
                    GraphRelation.target_entity_id.in_(entity_ids),
                ),
            )
        )
        removed_entities = session.execute(
            delete(GraphEntity).where(GraphEntity.tenant_id == tenant_id, GraphEntity.dataset_id == dataset_id)
        )
        return (cast(CursorResult, removed_relations).rowcount or 0) + (
            cast(CursorResult, removed_entities).rowcount or 0
        )

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_scope(
        *,
        account: Account | None,
        requested: set[str] | None,
        session: Session,
    ) -> set[str] | None:
        """Effective dataset scope for a retrieval.

        ``None`` means unrestricted within the tenant; an empty set means the
        caller has no permitted dataset and retrieval short-circuits.
        """
        if account is None:
            return requested
        from services.kb_permission_service import KBPermissionService

        granted = KBPermissionService.granted_resource_ids(
            account,
            resource_type=KBResourceType.DATASET,
            action=KBPermissionAction.DATASET_RETRIEVAL_RECALL.value,
            session=session,
        )
        if granted is None:  # owner/admin: unrestricted
            return requested
        if requested is None:
            return granted
        return set(requested) & granted

    @staticmethod
    def _match_entities(
        *,
        tenant_id: str,
        names: list[str],
        allowed_dataset_ids: set[str] | None,
        session: Session,
    ) -> tuple[list[GraphEntity], dict[str, float]]:
        """Match query entity names against stored entities.

        Returns ``(matched_entities, {entity_id: score})`` with scores 1.0 for
        exact name matches and 0.7 for prefix matches.
        """
        stmt = select(GraphEntity).where(GraphEntity.tenant_id == tenant_id)
        if allowed_dataset_ids is not None:
            stmt = stmt.where(GraphEntity.dataset_id.in_(allowed_dataset_ids))

        seen: dict[str, GraphEntity] = {}
        for name in names:
            pattern = name.lower().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            candidates = session.scalars(
                stmt.where(func.lower(GraphEntity.name).like(f"{pattern}%", escape="\\")).limit(MAX_CANDIDATES_PER_NAME)
            ).all()
            for entity in candidates:
                if entity.id not in seen:
                    seen[entity.id] = entity

        lower_names = {n.lower() for n in names}
        scores: dict[str, float] = {}
        for entity in seen.values():
            entity_name = entity.name.lower()
            if entity_name in lower_names:
                scores[entity.id] = 1.0
            elif any(entity_name.startswith(n) for n in lower_names):
                scores[entity.id] = 0.7
            else:
                scores[entity.id] = 0.3
        return list(seen.values()), scores

    @staticmethod
    def _traverse(
        *,
        start_ids: set[str],
        tenant_id: str,
        session: Session,
        records: dict[str, GraphEntityRecord],
        relations_out: dict[str, GraphRelationRecord],
        max_depth: int,
    ) -> None:
        """BFS over typed relations from ``start_ids``, collecting neighbors."""
        visited: set[str] = set(start_ids)
        edge_seen: set[str] = set()
        current_level: set[str] = start_ids
        level_of: dict[str, int] = dict.fromkeys(start_ids, 0)

        for level in range(1, max_depth + 1):
            if not current_level or len(relations_out) >= MAX_RELATIONS_PER_RETRIEVAL:
                break
            rows = session.scalars(
                select(GraphRelation).where(
                    GraphRelation.tenant_id == tenant_id,
                    or_(
                        GraphRelation.source_entity_id.in_(current_level),
                        GraphRelation.target_entity_id.in_(current_level),
                    ),
                )
            ).all()
            next_level: set[str] = set()
            for rel in rows:
                if rel.id in edge_seen:
                    continue
                edge_seen.add(rel.id)
                relations_out[rel.id] = GraphRelationRecord(
                    id=rel.id,
                    source_entity_id=rel.source_entity_id,
                    target_entity_id=rel.target_entity_id,
                    relation_type=rel.relation_type,
                    detail=rel.detail,
                )
                if len(relations_out) >= MAX_RELATIONS_PER_RETRIEVAL:
                    break
                for endpoint in (rel.source_entity_id, rel.target_entity_id):
                    if endpoint in visited:
                        continue
                    visited.add(endpoint)
                    level_of[endpoint] = level
                    next_level.add(endpoint)
            current_level = next_level

        if not visited:
            return
        entities = session.scalars(
            select(GraphEntity).where(GraphEntity.tenant_id == tenant_id, GraphEntity.id.in_(visited))
        ).all()
        for entity in entities:
            if entity.id in records:
                continue
            depth = level_of.get(entity.id, max_depth)
            score = 0.5**depth
            records[entity.id] = GraphService._to_record(entity, score=score)

    @staticmethod
    def _to_record(entity: GraphEntity, *, score: float) -> GraphEntityRecord:
        return GraphEntityRecord(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            dataset_id=entity.dataset_id,
            document_id=entity.document_id,
            score=score,
        )

    @staticmethod
    def _get_or_create_entity(
        *,
        tenant_id: str,
        dataset_id: str,
        document_id: str | None,
        name: str,
        entity_type: str | None,
        description: str | None,
        session: Session,
    ) -> tuple[GraphEntity, bool]:
        """Return ``(entity, created)`` where ``created`` reports whether the
        entity row was newly inserted (False when it already existed)."""
        entity = session.scalar(
            select(GraphEntity).where(
                GraphEntity.tenant_id == tenant_id,
                GraphEntity.dataset_id == dataset_id,
                func.lower(GraphEntity.name) == name.lower(),
                (GraphEntity.entity_type == entity_type) if entity_type else GraphEntity.entity_type.is_(None),
            )
        )
        if entity is None:
            entity = GraphEntity(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                document_id=document_id,
                name=name,
                entity_type=entity_type,
                description=description,
            )
            session.add(entity)
            session.flush()
            return entity, True
        if description and not entity.description:
            entity.description = description
        return entity, False

    @staticmethod
    def _relation_exists(
        *,
        tenant_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        session: Session,
    ) -> bool:
        return (
            session.scalar(
                select(GraphRelation.id).where(
                    GraphRelation.tenant_id == tenant_id,
                    GraphRelation.source_entity_id == source_entity_id,
                    GraphRelation.target_entity_id == target_entity_id,
                    GraphRelation.relation_type == relation_type,
                )
            )
            is not None
        )

    @staticmethod
    def _segment_content(segment: Any) -> str:
        if isinstance(segment, dict):
            return str(segment.get("content") or "")
        return str(getattr(segment, "content", "") or "")

    @staticmethod
    def _segment_document_id(segment: Any) -> str | None:
        if isinstance(segment, dict):
            return segment.get("document_id")
        return getattr(segment, "document_id", None)

    @staticmethod
    def _clean_name(value: Any) -> str:
        text = GraphService._clean_text(value)
        return text[:255] if text else ""

    @staticmethod
    def _clean_type(value: Any) -> str | None:
        text = GraphService._clean_text(value)
        return text[:64] if text else None

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
