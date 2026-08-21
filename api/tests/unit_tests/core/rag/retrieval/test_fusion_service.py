"""Unit tests for FusionService (requirement 1, task C2).

Covers normalization, cross-dataset deduplication, Reciprocal Rank Fusion
ranking and the B5 permission-whitelist filtration. Retrieval and permission
resolution are mocked so no database / vector store is required.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.rag.models.document import Document
from core.rag.retrieval.fusion_service import (
    FusionRecord,
    FusionService,
    FusionStrategy,
)


def _doc(content: str, *, score: float, dataset_id: str | None = None, document_id: str | None = None) -> Document:
    metadata: dict = {"score": score, "doc_name": content[:12]}
    if dataset_id:
        metadata["dataset_id"] = dataset_id
    if document_id:
        metadata["document_id"] = document_id
    return Document(page_content=content, metadata=metadata)


class TestNormalize:
    def test_normalize_builds_records_with_metadata(self):
        per = {
            "ds-1": [_doc("alpha", score=0.9, document_id="d-1")],
        }
        records = FusionService._normalize(per)
        assert len(records) == 1
        record = records[0]
        assert record.dataset_id == "ds-1"
        assert record.content == "alpha"
        assert record.metadata["score"] == 0.9


class TestDeduplicate:
    def test_same_content_same_document_dedup(self):
        # The same document surfaced from two datasets -> one record keeping the
        # higher score and accumulating both per-dataset sources.
        a = FusionRecord(dataset_id="ds-1", document_id="d-1", content="same text", metadata={"score": 0.9})
        b = FusionRecord(dataset_id="ds-2", document_id="d-1", content="same text", metadata={"score": 0.5})
        result = FusionService._deduplicate([a, b])
        assert len(result) == 1
        assert result[0].dataset_id == "ds-1"
        assert result[0].metadata["score"] == 0.9

    def test_distinct_content_kept(self):
        a = FusionRecord(dataset_id="ds-1", document_id="d-1", content="one", metadata={"score": 0.9})
        b = FusionRecord(dataset_id="ds-2", document_id="d-2", content="two", metadata={"score": 0.7})
        assert len(FusionService._deduplicate([a, b])) == 2


class TestFusionRanking:
    def _records(self):
        # ds-2 has one doc (s=0.5); ds-1 has two docs (s=0.9, s=0.8)
        return [
            FusionRecord(dataset_id="ds-1", document_id="d-1", content="top", metadata={"score": 0.9}),
            FusionRecord(dataset_id="ds-1", document_id="d-2", content="second", metadata={"score": 0.8}),
            FusionRecord(dataset_id="ds-2", document_id="d-3", content="other", metadata={"score": 0.5}),
        ]

    def test_rrf_ranks_by_cross_dataset_presence(self):
        records = self._records()
        fused = FusionService._fuse("q", records, strategy=FusionStrategy.RRF)
        scores = {r.document_id: r.score for r in fused}
        # RRF score is proportional to 1/(k+rank) within the item's own dataset:
        # d-1 and d-3 are rank-1 in their respective datasets; d-2 is rank-2.
        assert scores["d-1"] > scores["d-2"]
        assert scores["d-3"] > scores["d-2"]
        assert scores["d-1"] == scores["d-3"]

    def test_max_strategy_uses_original_score(self):
        records = self._records()
        fused = FusionService._fuse("q", records, strategy=FusionStrategy.MAX)
        by_doc = {r.document_id: r.score for r in fused}
        assert by_doc["d-1"] == 0.9
        assert by_doc["d-3"] == 0.5


class TestRetrieveWhitelist:
    def test_account_whitelist_filters_datasets(self):
        """B5: only datasets the account may retrieve from are queried."""
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        account.current_role = MagicMock()

        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value={"ds-1"},
        ) as mock_granted, patch.object(
            FusionService, "_retrieve_one", return_value=[]
        ) as mock_fetch:
            result = FusionService.retrieve(
                "q", ["ds-1", "ds-2"], session=MagicMock(), account=account
            )
            # only ds-1 is queried
            called_datasets = {call.args[1] for call in mock_fetch.call_args_list}
            assert called_datasets == {"ds-1"}
            mock_granted.assert_called_once()
            assert result.query == "q"

    def test_no_allowed_datasets_short_circuits(self):
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value=set(),
        ), patch.object(FusionService, "_retrieve_one", return_value=[]) as mock_fetch:
            result = FusionService.retrieve("q", ["ds-1"], session=MagicMock(), account=account)
            mock_fetch.assert_not_called()
            assert result.records == []

    def test_owner_unrestricted(self):
        """Owner (whitelist None) queries all requested datasets."""
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value=None,
        ), patch.object(FusionService, "_retrieve_one", return_value=[]) as mock_fetch:
            FusionService.retrieve("q", ["ds-1", "ds-2"], session=MagicMock(), account=account)
            called_datasets = {call.args[1] for call in mock_fetch.call_args_list}
            assert called_datasets == {"ds-1", "ds-2"}


class TestRetrieveFusionIntegration:
    def test_parallel_fetch_then_fuse(self):
        account = None
        # two datasets: ds-1 top score, ds-2 lower

        def fake_retrieve(query, dataset_id, top_k, score_threshold, account):  # noqa: ARG001
            if dataset_id == "ds-1":
                return [_doc("a", score=0.9, document_id="d-1"), _doc("b", score=0.8, document_id="d-2")]
            return [_doc("b", score=0.5, document_id="d-2"), _doc("c", score=0.4, document_id="d-3")]

        with patch.object(FusionService, "_retrieve_one", side_effect=fake_retrieve):
            result = FusionService.retrieve("q", ["ds-1", "ds-2"], session=MagicMock())
        # document d-2 appears in both datasets -> dedup keeps one and RRF boosts it
        # above single-dataset hits.
        docs = [r.document_id for r in result.records]
        assert "d-2" in docs
        assert len(result.records) == 3
        by_doc = {r.document_id: r.score for r in result.records}
        assert by_doc["d-2"] > by_doc["d-1"]
        assert by_doc["d-1"] > by_doc["d-3"]


class TestRetrieveAuditWiring:
    """D5 wiring: interactive fusion logs a RETRIEVAL audit row; runtime does not."""

    def test_interactive_account_logs_audit(self):
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        account.id = "account-1"
        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value=None,  # owner = unrestricted
        ), patch.object(FusionService, "_retrieve_one", return_value=[]), patch(
            "core.rag.retrieval.fusion_service.AuditLogService.record"
        ) as mock_record:
            result = FusionService.retrieve("q", ["ds-1", "ds-2"], session=MagicMock(), account=account)
            mock_record.assert_called_once()
            kwargs = mock_record.call_args.kwargs
            assert kwargs["tenant_id"] == "tenant-1"
            assert kwargs["log_type"].value == "retrieval"
            assert kwargs["action"] == "fusion.retrieve"
            assert kwargs["resource_type"] == "dataset"
            assert sorted(kwargs["detail"]["datasets"]) == ["ds-1", "ds-2"]
            assert result.query == "q"

    def test_runtime_no_account_skips_audit(self):
        with patch.object(FusionService, "_retrieve_one", return_value=[]), patch(
            "core.rag.retrieval.fusion_service.AuditLogService.record"
        ) as mock_record:
            FusionService.retrieve("q", ["ds-1"], session=MagicMock())
            mock_record.assert_not_called()


class TestRetrieveDatasetQueryWiring:
    """C2 extension: interactive fused retrieval records per-dataset DatasetQuery rows;
    runtime (no-account) retrieval does not."""

    def test_interactive_account_records_dataset_queries(self):
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        account.id = "account-1"
        docs = [_doc("a", score=0.9, document_id="d-1")]

        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value=None,
        ), patch.object(FusionService, "_retrieve_one", return_value=docs), patch(
            "core.rag.retrieval.fusion_service.AuditLogService.record"
        ), patch.object(
            FusionService, "_record_dataset_queries"
        ) as mock_rec:
            result = FusionService.retrieve("q", ["ds-1"], session=MagicMock(), account=account)

            mock_rec.assert_called_once()
            kwargs = mock_rec.call_args.kwargs
            assert kwargs["account_id"] == "account-1"
            assert kwargs["query"] == "q"
            assert kwargs["dataset_ids"] == ["ds-1"]
            assert result.query == "q"

    def test_no_hits_skips_dataset_queries(self):
        account = MagicMock()
        account.current_tenant_id = "tenant-1"
        account.id = "account-1"
        with patch(
            "core.rag.retrieval.fusion_service.KBPermissionService.granted_resource_ids",
            return_value=None,
        ), patch.object(FusionService, "_retrieve_one", return_value=[]), patch(
            "core.rag.retrieval.fusion_service.AuditLogService.record"
        ), patch.object(FusionService, "_record_dataset_queries") as mock_rec:
            FusionService.retrieve("q", ["ds-1"], session=MagicMock(), account=account)
            mock_rec.assert_not_called()

    def test_runtime_no_account_skips_dataset_queries(self):
        with patch.object(FusionService, "_retrieve_one", return_value=[]), patch.object(
            FusionService, "_record_dataset_queries"
        ) as mock_rec:
            FusionService.retrieve("q", ["ds-1"], session=MagicMock())
            mock_rec.assert_not_called()

    def test_record_dataset_queries_writes_rows_in_independent_session(self):
        """Prepare one DatasetQuery per dataset, committed via an independent session."""

        class _FakeSession:
            def __init__(self):
                self.added = []

            def add_all(self, rows):
                self.added.extend(rows)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake = _FakeSession()
        factory = MagicMock()
        factory.begin.return_value = fake

        with (
            patch("core.rag.retrieval.fusion_service.db", SimpleNamespace(engine=MagicMock())),
            patch("core.rag.retrieval.fusion_service.sessionmaker", return_value=factory),
        ):
            FusionService._record_dataset_queries(
                query="q", dataset_ids=["ds-1", "ds-2"], account_id="acc-1"
            )

        dataset_ids = [row.dataset_id for row in fake.added]
        assert dataset_ids == ["ds-1", "ds-2"]
        for row in fake.added:
            assert row.created_by_role == "account"
            assert row.source == "hit_testing"
            assert row.created_by == "acc-1"

    def test_record_dataset_queries_failure_swallowed(self):
        """A stat-log failure must not raise and must not break the caller."""

        def _boom(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("db down")

        with patch(
            "core.rag.retrieval.fusion_service.sessionmaker", side_effect=_boom
        ):
            FusionService._record_dataset_queries(
                query="q", dataset_ids=["ds-1"], account_id="acc-1"
            )
