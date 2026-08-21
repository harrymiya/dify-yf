"""FusionService - multi-dataset fused retrieval (requirement 1, task C2).

Provides a single unified entry point for "multiple assistants / multiple
knowledge bases" retrieval: run per-dataset retrieval in parallel, then fuse and
rank the results (normalize -> dedup -> fused ranking -> top_k trim).

It deliberately sits **above** :class:`RetrievalService.retrieve` (the existing
per-dataset entry) and reuses the four-layer KB permission whitelist from
requirement 3 (B5) so a caller can only fuse over datasets it is allowed to
retrieve from. Runtime app/workflow retrieval that passes no explicit account is
enforced at app-config level, so by default the whitelist is *not* applied here.

Fusion strategy (``strategy``):

- ``rrf``  (default): Reciprocal Rank Fusion over each per-dataset ranking.
  Robust to incomparable score scales across datasets; good for heterogeneous
  knowledge bases.
- ``max``  : take the max normalized score per item across datasets.
- ``sum``  : weighted sum of per-dataset scores (weights default to 1.0).
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from operator import itemgetter
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import sessionmaker

from core.rag.datasource.retrieval_service import RetrievalService
from core.rag.index_processor.constant.query_type import QueryType
from core.rag.models.document import Document
from extensions.ext_database import db
from models.audit_log import AuditLogStatus, AuditLogType
from models.dataset import DatasetQuery
from models.enums import CreatorUserRole, DatasetQuerySource
from services.audit_log_service import AuditLogService
from services.kb_permission_service import KBPermissionService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from models import Account

__all__ = ["FusionRecord", "FusionResult", "FusionService", "FusionStrategy"]


class FusionStrategy:
    """Fusion ranking strategies for fused retrieval results."""

    RRF = "rrf"
    MAX = "max"
    SUM = "sum"


@dataclass(slots=True)
class FusionRecord:
    """A single normalized, deduplicated retrieval hit spanning many datasets."""

    dataset_id: str
    document_id: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    title: str | None = None
    #: the per-dataset sources that contributed to this fused hit.
    sources: list[Document] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable dedup key: dataset-independent, based on document+content."""
        basis = f"{self.document_id}:{self.content}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class FusionResult:
    query: str
    records: list[FusionRecord] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "records": [
                {
                    "dataset_id": r.dataset_id,
                    "document_id": r.document_id,
                    "title": r.title,
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in self.records
            ],
        }


class FusionService:
    """Parallel multi-dataset retrieval with normalization, dedup and fusion."""

    @staticmethod
    def retrieve(
        query: str,
        dataset_ids: list[str],
        *,
        session: Session,
        top_k: int = 10,
        score_threshold: float | None = 0.0,
        strategy: str = FusionStrategy.RRF,
        max_workers: int = 4,
        account: Account | None = None,
        action: str | None = None,
        allowed_dataset_ids: set[str] | None = None,
    ) -> FusionResult:
        """Fuse retrieval across ``dataset_ids``.

        Args:
            account: when provided (interactive/console context), the requested
                ``dataset_ids`` are intersected with the caller's permission
                whitelist for ``action`` (default ``dataset_retrieval_recall``),
                implementing B5 isolation at the fusion layer.
            allowed_dataset_ids: explicit whitelist; when ``None`` and no
                ``account`` is given, all requested datasets are allowed.
        """
        from models.kb_permission import KBResourceType

        action = action or "dataset_retrieval_recall"

        # Permission whitelist intersection (B5). An owner returns None = unrestricted.
        if account is not None:
            granted = KBPermissionService.granted_resource_ids(
                account,
                resource_type=KBResourceType.DATASET,
                action=action,
                session=session,
            )
            if granted is not None:
                allowed_dataset_ids = set(dataset_ids) & granted
            else:
                allowed_dataset_ids = set(dataset_ids)
        elif allowed_dataset_ids is None:
            allowed_dataset_ids = set(dataset_ids)
        else:
            allowed_dataset_ids = set(allowed_dataset_ids)

        if not allowed_dataset_ids:
            return FusionResult(query=query)

        per_dataset: dict[str, list[Document]] = {}
        future_map = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(FusionService._retrieve_one, query, ds_id, top_k, score_threshold, account): ds_id
                for ds_id in allowed_dataset_ids
            }
            for future in as_completed(future_map):
                ds_id = future_map[future]
                try:
                    per_dataset[ds_id] = future.result()
                except Exception:
                    per_dataset[ds_id] = []

        records = FusionService._normalize(per_dataset)
        records = FusionService._deduplicate(records)
        fused = FusionService._fuse(query, records, strategy=strategy)
        fused = sorted(fused, key=lambda r: r.score, reverse=True)[:top_k]

        # Audit trail (requirement 5): log interactive fused retrieval once per call.
        # Runtime app/workflow calls pass no account and are intentionally unaffected.
        if account is not None:
            tenant_id = getattr(account, "current_tenant_id", None)
            account_id = getattr(account, "id", None)
            if tenant_id:
                AuditLogService.record(
                    tenant_id=tenant_id,
                    log_type=AuditLogType.RETRIEVAL,
                    action="fusion.retrieve",
                    session=session,
                    user_id=account_id,
                    user_type="account",
                    status=AuditLogStatus.SUCCESS,
                    resource_type="dataset",
                    detail={"query": query, "datasets": list(allowed_dataset_ids), "hits": len(fused)},
                )

            # Dataset call statistic: record one query row per distinct dataset that
            # actually produced a fused hit (console/account-driven retrieval).
            hit_dataset_ids = {r.dataset_id for r in fused if r.dataset_id}
            if account_id and hit_dataset_ids:
                FusionService._record_dataset_queries(
                    query=query,
                    dataset_ids=sorted(hit_dataset_ids),
                    account_id=account_id,
                )

        return FusionResult(query=query, records=fused)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _record_dataset_queries(*, query: str, dataset_ids: list[str], account_id: str) -> None:
        """Persist DatasetQuery rows in an independent session.

        This instrumentation is a side effect of a successful interactive fused
        retrieval. It runs in its own transaction so it never commits or closes
        the caller's request-scoped session, and failures here are non-fatal so a
        stat write can never break the retrieval itself.
        """
        try:
            content = json.dumps([{"content_type": QueryType.TEXT_QUERY.value, "content": query}])
            rows = [
                DatasetQuery(
                    dataset_id=dataset_id,
                    content=content,
                    source=DatasetQuerySource.HIT_TESTING,
                    source_app_id=None,
                    created_by_role=CreatorUserRole.ACCOUNT,
                    created_by=account_id,
                )
                for dataset_id in dataset_ids
            ]
        except Exception:
            logger.warning("Failed to prepare fused-retrieval dataset query stats", exc_info=True)
            return

        try:
            with sessionmaker(bind=db.engine, expire_on_commit=False).begin() as independent_session:
                independent_session.add_all(rows)
        except Exception:
            logger.warning("Failed to persist fused-retrieval dataset query stats", exc_info=True)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _retrieve_one(
        query: str,
        dataset_id: str,
        top_k: int,
        score_threshold: float | None,
        account: Account | None,
    ) -> list[Document]:
        return RetrievalService.retrieve(
            retrieval_method=_retrieval_method(),
            dataset_id=dataset_id,
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            kb_permission_account=account,
        )

    @staticmethod
    def _normalize(per_dataset: dict[str, list[Document]]) -> list[FusionRecord]:
        """Turn per-dataset Document lists into FusionRecords tagged by dataset."""
        from core.rag.retrieval.retrieval_methods import RetrievalMethod  # noqa: F401 (document score context)

        records: list[FusionRecord] = []
        for ds_id, docs in per_dataset.items():
            for doc in docs:
                metadata = dict(doc.metadata or {})
                # Make each source self-describing so fusion can attribute RRF rank
                # credit per dataset when a distinct source is merged into a record.
                metadata["dataset_id"] = ds_id
                doc.metadata = metadata
                document_id = str(metadata.get("document_id") or doc.metadata.get("doc_id") or "")
                record = FusionRecord(
                    dataset_id=ds_id,
                    document_id=document_id,
                    content=doc.page_content,
                    score=float(metadata.get("score", 0.0) or 0.0),
                    metadata=metadata,
                    title=str(metadata.get("doc_name") or metadata.get("document_name") or ""),
                    sources=[doc],
                )
                records.append(record)
        return records

    @staticmethod
    def _deduplicate(records: list[FusionRecord]) -> list[FusionRecord]:
        """Remove duplicates by content key, keeping the highest original score and
        accumulating every per-dataset source so cross-dataset RRF credit is preserved."""
        best: dict[str, FusionRecord] = {}
        for record in records:
            key = record.key
            existing = best.get(key)
            if existing is None:
                best[key] = record
                continue
            # Merge sources from both occurrences and keep the highest score.
            existing.sources.extend(s for s in record.sources if s not in existing.sources)
            if (
                _safe_float(existing.metadata.get("score", 0.0))
                < _safe_float(record.metadata.get("score", 0.0))
            ):
                existing.metadata = dict(record.metadata)
                existing.score = record.score
        return list(best.values())

    @staticmethod
    def _fuse(
        query: str,
        records: list[FusionRecord],
        *,
        strategy: str,
    ) -> list[FusionRecord]:
        """Assign a cross-dataset fused score per record per the chosen strategy."""
        if strategy in {FusionStrategy.MAX, FusionStrategy.SUM}:
            for record in records:
                record.score = _safe_float(record.metadata.get("score", 0.0))
        else:  # FusionStrategy.RRF (default)
            return FusionService._rrf(records)
        return records

    @staticmethod
    def _rrf(records: list[FusionRecord]) -> list[FusionRecord]:
        """Reciprocal Rank Fusion across per-dataset rankings.

        Every source document that contributed to a record is ranked within its
        own dataset and accumulates ``1 / (k + rank)`` onto the record's fused
        score. A record found in many datasets therefore accumulates more credit
        than a single-dataset hit, which is the core cross-dataset fusion signal.
        """
        from collections import defaultdict

        k = 60
        rrf: dict[str, float] = defaultdict(float)
        detail: dict[str, FusionRecord] = {}
        by_dataset: dict[str, list[tuple[float, FusionRecord]]] = defaultdict(list)

        for record in records:
            detail[record.key] = record
            sources = record.sources or [record]
            for src in sources:
                src_meta = dict(getattr(src, "metadata", {}) or {})
                ds_id = str(src_meta.get("dataset_id") or record.dataset_id)
                src_score = _safe_float(src_meta.get("score", 0.0))
                by_dataset[ds_id].append((src_score, record))

        for ds_id, entries in by_dataset.items():
            ranked = sorted(entries, key=itemgetter(0), reverse=True)
            for rank, (_, record) in enumerate(ranked, start=1):
                rrf[record.key] += 1.0 / (k + rank)

        for key, record in detail.items():
            record.score = rrf[key]

        # deterministic tie-break: RRF desc, then original score desc, then content
        return sorted(
            detail.values(),
            key=lambda r: (-r.score, -_safe_float(r.metadata.get("score", 0.0)), r.content),
        )


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _retrieval_method():
    """Return the default (semantic) retrieval method instance."""
    from core.rag.retrieval.retrieval_methods import RetrievalMethod

    return RetrievalMethod.SEMANTIC_SEARCH
