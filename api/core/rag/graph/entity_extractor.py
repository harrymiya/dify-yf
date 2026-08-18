"""GraphEntityExtractor - LLM-based entity/relation extraction (task C4).

Extracts knowledge-graph nodes/edges from a text (document segment while
building) or a retrieval query (while searching). The default implementation
calls the tenant's default LLM and parses strict JSON output.

The extraction function is deliberately a plain callable with a stable
signature (``(text, *, tenant_id, session) -> (entities, relations)``) so
:class:`~core.rag.graph.graph_service.GraphService` can be unit-tested with a
fake extractor and the LLM call can be swapped for a cheaper rule-based
extractor later without touching graph traversal logic.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from core.model_manager import ModelManager
from core.rag.graph.prompts import ENTITY_EXTRACTION_PROMPT, QUERY_ENTITY_EXTRACTION_PROMPT
from graphon.model_runtime.entities.llm_entities import LLMResult
from graphon.model_runtime.entities.message_entities import SystemPromptMessage, UserPromptMessage
from graphon.model_runtime.entities.model_entities import ModelType

logger = logging.getLogger(__name__)

#: Extraction callable signature used across the graph module.
Extractor = Callable[[str, Any], tuple[list[dict], list[dict]]]

__all__ = ["Extractor", "GraphEntityExtractor"]


class GraphEntityExtractor:
    """Extract graph entities (and relations) from text via the default LLM."""

    #: temperature used for extraction; low to keep output deterministic.
    MODEL_PARAMETERS: dict[str, Any] = {"temperature": 0.2}

    @staticmethod
    def extract(
        text: str,
        *,
        tenant_id: str,
        session: Any,
        for_query: bool = False,
    ) -> tuple[list[dict], list[dict]]:
        """Extract ``(entities, relations)`` from ``text``.

        In query mode (``for_query=True``) only entities are returned, which is
        cheaper and sufficient to enter graph retrieval.
        """
        if not text or not text.strip():
            return [], []

        prompt = QUERY_ENTITY_EXTRACTION_PROMPT if for_query else ENTITY_EXTRACTION_PROMPT
        if for_query:
            rendered = prompt.format(query=text)
        else:
            rendered = prompt.format(text=text)

        prompt_messages = [
            SystemPromptMessage(content="You output strict JSON only."),
            UserPromptMessage(content=rendered),
        ]

        raw = GraphEntityExtractor._invoke_llm(prompt_messages, tenant_id=tenant_id)
        payload = GraphEntityExtractor._parse_json_output(raw) or {}

        entities = payload.get("entities") or []
        relations = [] if for_query else (payload.get("relations") or [])
        return entities, relations

    # ------------------------------------------------------------------ #
    @staticmethod
    def _invoke_llm(prompt_messages: list, *, tenant_id: str) -> str:
        model_manager = ModelManager.for_tenant(tenant_id=tenant_id)
        model_instance = model_manager.get_default_model_instance(tenant_id=tenant_id, model_type=ModelType.LLM)
        result = model_instance.invoke_llm(
            prompt_messages=prompt_messages,
            model_parameters=GraphEntityExtractor.MODEL_PARAMETERS,
            stream=False,
        )
        if not isinstance(result, LLMResult):
            raise ValueError("Expected LLMResult when stream=False")
        return result.message.get_text_content() or ""

    @staticmethod
    def _parse_json_output(raw: str) -> dict[str, Any] | None:
        """Parse the model output into a dict, tolerating markdown fences/junk."""
        if not raw:
            return None
        text = raw.strip()
        # strip markdown code fences
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # last resort: extract the outermost {...} span
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                payload = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, TypeError):
                return None
        if not isinstance(payload, dict):
            return None
        return payload
