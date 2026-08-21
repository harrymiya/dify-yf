"""Unit tests for kb-graph retrieval instrumentation (task C3).

Covers the DatasetQuery instrumentation added to the kb-graph ``retrieve``
endpoint: a row is prepared per successful graph retrieval and committed in an
independent session; failures are swallowed so retrieval is never broken.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from controllers.console.kb_graphs import KBGraphRetrieveApi


class TestRecordDatasetQuery:
    def test_records_dataset_query_in_independent_session(self):
        class _FakeSession:
            def __init__(self):
                self.added = []

            def add(self, row):
                self.added.append(row)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake = _FakeSession()
        factory = MagicMock()
        factory.begin.return_value = fake

        with (
            patch("controllers.console.kb_graphs.db", SimpleNamespace(engine=MagicMock())),
            patch("controllers.console.kb_graphs.sessionmaker", return_value=factory),
        ):
            KBGraphRetrieveApi._record_dataset_query(
                query="what is dify",
                dataset_id="ds-1",
                account_id="acc-1",
            )

        assert len(fake.added) == 1
        row = fake.added[0]
        assert row.dataset_id == "ds-1"
        assert row.created_by == "acc-1"
        assert row.created_by_role == "account"
        assert row.source == "hit_testing"
        assert row.source_app_id is None
        assert "what is dify" in row.content

    def test_failure_swallowed(self):
        def _boom(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("db down")

        with patch("controllers.console.kb_graphs.sessionmaker", side_effect=_boom):
            KBGraphRetrieveApi._record_dataset_query(
                query="q",
                dataset_id="ds-1",
                account_id="acc-1",
            )
