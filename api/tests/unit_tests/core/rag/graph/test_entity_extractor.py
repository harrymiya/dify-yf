"""Unit tests for GraphEntityExtractor (requirement 1, task C4).

Covers the LLM-output JSON parser and the extraction flow. The LLM call is
patched so no model provider / database is required.
"""

from unittest.mock import MagicMock, patch

from core.rag.graph.entity_extractor import GraphEntityExtractor


class TestParseJsonOutput:
    def test_plain_json(self):
        payload = GraphEntityExtractor._parse_json_output('{"entities": [{"name": "Dify"}]}')
        assert payload == {"entities": [{"name": "Dify"}]}

    def test_fenced_json(self):
        raw = '```json\n{"entities": [{"name": "Dify"}]}\n```'
        assert GraphEntityExtractor._parse_json_output(raw) == {"entities": [{"name": "Dify"}]}

    def test_trailing_text_stripped(self):
        raw = 'Here you go:\n{"entities": []}\nHope that helps.'
        assert GraphEntityExtractor._parse_json_output(raw) == {"entities": []}

    def test_garbage_returns_none(self):
        assert GraphEntityExtractor._parse_json_output("not json at all") is None
        assert GraphEntityExtractor._parse_json_output("") is None


class TestExtract:
    @patch.object(GraphEntityExtractor, "_invoke_llm")
    def test_extract_returns_entities_and_relations(self, mock_invoke):
        mock_invoke.return_value = (
            '{"entities": [{"name": "Dify", "type": "product"}],'
            ' "relations": [{"source": "Dify", "target": "RAG", "type": "uses"}]}'
        )

        entities, relations = GraphEntityExtractor.extract(
            "Dify uses RAG for retrieval.", tenant_id="tenant-1", session=MagicMock()
        )

        assert entities == [{"name": "Dify", "type": "product"}]
        assert relations == [{"source": "Dify", "target": "RAG", "type": "uses"}]
        mock_invoke.assert_called_once()

    @patch.object(GraphEntityExtractor, "_invoke_llm")
    def test_extract_query_mode_returns_entities_only(self, mock_invoke):
        mock_invoke.return_value = '{"entities": [{"name": "Dify"}], "relations": []}'

        entities, relations = GraphEntityExtractor.extract(
            "how does Dify work?", tenant_id="tenant-1", session=MagicMock(), for_query=True
        )
        assert entities == [{"name": "Dify"}]
        assert relations == []
        mock_invoke.assert_called_once()

    @patch.object(GraphEntityExtractor, "_invoke_llm")
    def test_extract_empty_text_short_circuits(self, mock_invoke):
        entities, relations = GraphEntityExtractor.extract("  ", tenant_id="tenant-1", session=MagicMock())
        assert entities == []
        assert relations == []
        mock_invoke.assert_not_called()

    @patch.object(GraphEntityExtractor, "_invoke_llm")
    def test_extract_invalid_llm_output_falls_back_to_empty(self, mock_invoke):
        mock_invoke.return_value = "totally not json"
        entities, relations = GraphEntityExtractor.extract("some text", tenant_id="tenant-1", session=MagicMock())
        assert entities == []
        assert relations == []


class TestInvokeLlm:
    def test_invoke_llm_returns_text_content(self):
        from graphon.model_runtime.entities.llm_entities import LLMResult, LLMUsage
        from graphon.model_runtime.entities.message_entities import AssistantPromptMessage

        usage = LLMUsage.model_validate(
            {
                "prompt_tokens": 1,
                "prompt_unit_price": 0,
                "prompt_price_unit": 0,
                "prompt_price": 0,
                "completion_tokens": 1,
                "completion_unit_price": 0,
                "completion_price_unit": 0,
                "completion_price": 0,
                "total_tokens": 2,
                "total_price": 0,
                "currency": "USD",
                "latency": 0.0,
            }
        )
        result = LLMResult(
            model="test-model",
            message=AssistantPromptMessage(content='{"entities": []}'),
            usage=usage,
        )
        manager = MagicMock()
        instance = manager.get_default_model_instance.return_value
        instance.invoke_llm.return_value = result
        with patch("core.rag.graph.entity_extractor.ModelManager.for_tenant", return_value=manager):
            text = GraphEntityExtractor._invoke_llm([], tenant_id="tenant-1")
        assert '{"entities": []}' in text
