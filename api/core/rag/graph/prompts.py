"""Prompt templates for knowledge-graph entity extraction (requirement 1, C4).

Two prompts: a full document/segment extraction (entities + relations, used to
build the graph) and a lightweight query extraction (entities only, used to
enter graph retrieval). Both request strict JSON so the output can be parsed
without a tool/function-calling contract.
"""

ENTITY_EXTRACTION_PROMPT = """You are a knowledge-graph builder. Extract the named entities and the typed
relations between them from the text below.

Rules:
- Only extract entities that are meaningful domain objects (products, technologies,
  systems, organizations, people, concepts). Skip stop words and generic filler.
- A relation must reference two entities that both appear in your extracted list.
- Keep entity names short and canonical (do not repeat the same entity with variants).
- Use `type` from a small set: product | technology | system | organization | person | concept.
- Respond ONLY with valid JSON, no markdown fences, no commentary.

Output schema:
{{"entities": [{{"name": "string", "type": "string", "description": "string"}}],
 "relations": [{{"source": "string", "target": "string", "type": "string", "description": "string"}}]}}

Text:
{text}
"""

QUERY_ENTITY_EXTRACTION_PROMPT = """You are a knowledge-graph query parser. Extract the named entities the user is
asking about from the query below.

Rules:
- Extract only concrete named entities (products, technologies, systems, organizations,
  people, concepts). Skip verbs, stop words and generic words.
- Keep entity names short and canonical.
- Respond ONLY with valid JSON, no markdown fences, no commentary.

Output schema:
{{"entities": [{{"name": "string", "type": "string"}}]}}

Query:
{query}
"""
