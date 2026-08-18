"""Unit tests for GraphService (requirement 1, tasks C4/C5).

Uses the shared SQLite session so build/retrieval logic runs against real ORM
queries. Extraction and permission resolution are injectable / driven by real
grant rows, so no model provider is required.
"""

from unittest.mock import MagicMock

from core.rag.graph.graph_service import GraphService
from models.account import TenantAccountRole
from models.graph import GraphEntity, GraphRelation
from models.kb_permission import KBPermissionAction, KBPermissionGrant, KBResourceType, KBSubjectType

TENANT = "tenant-1"


def _account(account_id="acc-1", role=TenantAccountRole.EDITOR, tenant_id=TENANT):
    account = MagicMock()
    account.id = account_id
    account.current_tenant_id = tenant_id
    account.current_role = role
    return account


def _insert_entity(session, *, entity_id, dataset_id, name, entity_type="concept", document_id=None):
    entity = GraphEntity(
        tenant_id=TENANT,
        dataset_id=dataset_id,
        document_id=document_id,
        name=name,
        entity_type=entity_type,
    )
    entity.id = entity_id
    session.add(entity)
    return entity


def _insert_relation(session, *, source_id, target_id, relation_type="depends_on", relation_id=None):
    relation = GraphRelation(
        tenant_id=TENANT,
        source_entity_id=source_id,
        target_entity_id=target_id,
        relation_type=relation_type,
        detail={},
    )
    if relation_id:
        relation.id = relation_id
    session.add(relation)
    return relation


def _grant(session, *, account_id, dataset_id, action=KBPermissionAction.DATASET_RETRIEVAL_RECALL.value):
    session.add(
        KBPermissionGrant(
            tenant_id=TENANT,
            subject_type=KBSubjectType.ACCOUNT,
            subject_id=account_id,
            resource_type=KBResourceType.DATASET,
            resource_id=dataset_id,
            action=action,
        )
    )


def _query_extractor(*query_names: str):
    """Extractor that returns the given entity names for every query text."""

    def extractor(text, *, tenant_id, session, for_query=False):  # noqa: ARG001
        return [{"name": name} for name in query_names], []

    return extractor


class TestBuildGraph:
    def test_build_creates_entities_and_relations(self, sqlite_session):
        def extractor(text, *, tenant_id, session):  # noqa: ARG001
            return (
                [
                    {"name": "Dify", "type": "product", "description": "LLM platform"},
                    {"name": "RAG", "type": "technology"},
                ],
                [{"source": "Dify", "target": "RAG", "type": "depends_on"}],
            )

        result = GraphService.build_graph(
            tenant_id=TENANT,
            dataset_id="ds-1",
            document_id="doc-1",
            segments=[{"content": "Dify uses RAG.", "document_id": "doc-1"}],
            session=sqlite_session,
            extractor=extractor,
        )
        sqlite_session.flush()

        assert result.entities_created == 2
        assert result.entities_matched == 0
        assert result.relations_created == 1
        assert result.segments_processed == 1

        entities = sqlite_session.query(GraphEntity).all()
        assert {e.name for e in entities} == {"Dify", "RAG"}
        assert all(e.tenant_id == TENANT for e in entities)
        assert all(e.dataset_id == "ds-1" for e in entities)
        assert all(e.document_id == "doc-1" for e in entities)

        relations = sqlite_session.query(GraphRelation).all()
        assert len(relations) == 1
        assert relations[0].relation_type == "depends_on"

    def test_build_is_idempotent(self, sqlite_session):
        def extractor(text, *, tenant_id, session):  # noqa: ARG001
            return (
                [{"name": "Dify", "type": "product"}],
                [{"source": "Dify", "target": "RAG", "type": "uses"}],
            )

        segments = [{"content": "Dify uses RAG.", "document_id": "doc-1"}]
        first = GraphService.build_graph(
            tenant_id=TENANT,
            dataset_id="ds-1",
            document_id=None,
            segments=segments,
            session=sqlite_session,
            extractor=extractor,
        )
        sqlite_session.flush()
        second = GraphService.build_graph(
            tenant_id=TENANT,
            dataset_id="ds-1",
            document_id=None,
            segments=segments,
            session=sqlite_session,
            extractor=extractor,
        )
        sqlite_session.flush()

        assert first.entities_created == 2
        assert second.entities_created == 0
        assert second.entities_matched == 2
        assert second.relations_created == 0
        assert sqlite_session.query(GraphEntity).count() == 2
        assert sqlite_session.query(GraphRelation).count() == 1

    def test_build_skips_failing_segments(self, sqlite_session):
        def extractor(text, *, tenant_id, session):  # noqa: ARG001
            if text == "bad":
                raise ValueError("boom")
            return ([{"name": "Dify", "type": "product"}], [])

        result = GraphService.build_graph(
            tenant_id=TENANT,
            dataset_id="ds-1",
            document_id=None,
            segments=[{"content": "good"}, {"content": "bad"}, {"content": ""}],
            session=sqlite_session,
            extractor=extractor,
        )
        sqlite_session.flush()

        assert result.segments_processed == 1
        assert result.segments_skipped == 2
        assert sqlite_session.query(GraphEntity).count() == 1

    def test_build_orphan_relations_create_entities(self, sqlite_session):
        def extractor(text, *, tenant_id, session):  # noqa: ARG001
            # relation references names absent from the entity list
            return ([{"name": "Dify", "type": "product"}], [{"source": "Dify", "target": "RAG", "type": "uses"}])

        result = GraphService.build_graph(
            tenant_id=TENANT,
            dataset_id="ds-1",
            document_id=None,
            segments=[{"content": "Dify uses RAG."}],
            session=sqlite_session,
            extractor=extractor,
        )
        sqlite_session.flush()

        assert result.entities_created == 2
        assert sqlite_session.query(GraphEntity).count() == 2


class TestRetrieveMatching:
    def test_retrieve_exact_and_prefix_match(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        _insert_entity(sqlite_session, entity_id="e-2", dataset_id="ds-1", name="Dify Cloud", entity_type="product")
        sqlite_session.commit()

        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=None,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1"},
            extractor=_query_extractor("Dify"),
        )

        names = {r.name: r.score for r in result.records}
        assert set(names) == {"Dify", "Dify Cloud"}
        assert names["Dify"] == 1.0
        assert names["Dify Cloud"] == 0.7

    def test_retrieve_no_match_returns_empty(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        sqlite_session.commit()

        result = GraphService.retrieve(
            "Unrelated",
            tenant_id=TENANT,
            account=None,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1"},
            extractor=_query_extractor("Unrelated"),
        )
        assert result.records == []
        assert result.relations == []

    def test_retrieve_traverses_relations(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        _insert_entity(sqlite_session, entity_id="e-2", dataset_id="ds-1", name="RAG", entity_type="technology")
        _insert_relation(sqlite_session, source_id="e-1", target_id="e-2", relation_type="depends_on")
        sqlite_session.commit()

        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=None,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1"},
            extractor=_query_extractor("Dify"),
        )

        names = {r.name: r.score for r in result.records}
        assert "Dify" in names
        assert "RAG" in names
        # traversed neighbor ranks below the matched entity
        assert names["Dify"] == 1.0
        assert names["RAG"] == 0.5
        assert len(result.relations) == 1
        assert result.relations[0].relation_type == "depends_on"


class TestC5PermissionIsolation:
    def test_non_owner_only_granted_datasets(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        _insert_entity(sqlite_session, entity_id="e-2", dataset_id="ds-2", name="Dify", entity_type="product")
        _grant(sqlite_session, account_id="acc-1", dataset_id="ds-1")
        sqlite_session.commit()

        account = _account(account_id="acc-1", role=TenantAccountRole.EDITOR)
        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=account,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1", "ds-2"},
            extractor=_query_extractor("Dify"),
        )

        datasets = {r.dataset_id for r in result.records}
        assert datasets == {"ds-1"}

    def test_non_owner_scope_intersection(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-2", dataset_id="ds-2", name="Dify", entity_type="product")
        _grant(sqlite_session, account_id="acc-1", dataset_id="ds-2")
        sqlite_session.commit()

        account = _account(account_id="acc-1", role=TenantAccountRole.EDITOR)
        # requested scope {ds-1} does not intersect the granted {ds-2}
        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=account,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1"},
            extractor=_query_extractor("Dify"),
        )
        assert result.records == []

    def test_non_owner_no_grants_short_circuits(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        sqlite_session.commit()

        account = _account(account_id="acc-1", role=TenantAccountRole.EDITOR)
        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=account,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1"},
            extractor=_query_extractor("Dify"),
        )
        assert result.records == []
        assert result.relations == []

    def test_owner_unrestricted_across_requested_datasets(self, sqlite_session):
        _insert_entity(sqlite_session, entity_id="e-1", dataset_id="ds-1", name="Dify", entity_type="product")
        _insert_entity(sqlite_session, entity_id="e-2", dataset_id="ds-2", name="Dify", entity_type="product")
        sqlite_session.commit()

        account = _account(account_id="acc-1", role=TenantAccountRole.OWNER)
        result = GraphService.retrieve(
            "Dify",
            tenant_id=TENANT,
            account=account,
            session=sqlite_session,
            allowed_dataset_ids={"ds-1", "ds-2"},
            extractor=_query_extractor("Dify"),
        )
        assert {r.dataset_id for r in result.records} == {"ds-1", "ds-2"}
