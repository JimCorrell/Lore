import json
import logging
from dataclasses import dataclass, field

import anthropic
import tiktoken

from app.models.domain import Domain

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "claude-sonnet-4-6"
CHUNK_SIZE_TOKENS = 1_500
CHUNK_OVERLAP_TOKENS = 150
MAX_CHUNKS_PER_DOC = 100

_ENCODING = tiktoken.get_encoding("cl100k_base")

EXTRACTION_TOOL = {
    "name": "record_extractions",
    "description": "Record all named entities and relationships found in this text passage.",
    "input_schema": {
        "type": "object",
        "required": ["entities", "relationships"],
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "name",
                        "type",
                        "raw_excerpt",
                        "synthesized_description",
                    ],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "attributes": {"type": "object", "default": {}},
                        "raw_excerpt": {"type": "string"},
                        "synthesized_description": {"type": "string"},
                    },
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "from_entity_name",
                        "relation_type",
                        "to_entity_name",
                        "raw_excerpt",
                        "synthesized_description",
                    ],
                    "properties": {
                        "from_entity_name": {"type": "string"},
                        "relation_type": {"type": "string"},
                        "to_entity_name": {"type": "string"},
                        "raw_excerpt": {"type": "string"},
                        "synthesized_description": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass
class ExtractedEntity:
    name: str
    type: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    raw_excerpt: str = ""
    synthesized_description: str = ""


@dataclass
class ExtractedRelationship:
    from_entity_name: str
    relation_type: str
    to_entity_name: str
    raw_excerpt: str
    synthesized_description: str


@dataclass
class ChunkResult:
    passage_index: int
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]
    extraction_model: str


def _chunk_text(text: str) -> list[tuple[str, int]]:
    """Return (chunk_text, passage_index) pairs."""
    tokens = _ENCODING.encode(text)
    stride = CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS
    chunks = []
    for i, start in enumerate(range(0, len(tokens), stride)):
        if i >= MAX_CHUNKS_PER_DOC:
            logger.warning(
                "Document exceeds MAX_CHUNKS_PER_DOC=%d; truncating", MAX_CHUNKS_PER_DOC
            )
            break
        end = start + CHUNK_SIZE_TOKENS
        chunk_tokens = tokens[start:end]
        chunk_text = _ENCODING.decode(chunk_tokens)
        chunks.append((chunk_text, i))
        if end >= len(tokens):
            break
    return chunks


def _build_system_prompt(domain: Domain) -> str:
    relation_lines = "\n".join(
        f"  - {rt['type']} (bidirectional: {'yes' if rt.get('bidirectional') else 'no'})"
        for rt in domain.relation_types
    )
    return (
        f'You are a named entity extractor for the "{domain.name}" knowledge domain.\n'
        "Your task: identify ALL named entities and relationships in the provided text passage.\n\n"
        f"ENTITY TYPES allowed in this domain:\n  {', '.join(domain.entity_types)}\n\n"
        f"RELATION TYPES allowed in this domain:\n{relation_lines}\n\n"
        f"EXTRACTION HINTS:\n{domain.extraction_hints or 'None provided.'}\n\n"
        f"ATTRIBUTE SCHEMA (capture these per entity type when mentioned):\n"
        f"{json.dumps(domain.attribute_schema, indent=2)}\n\n"
        "RULES:\n"
        "- Only extract entities that are EXPLICITLY NAMED in this passage.\n"
        "- Do not invent or infer entities not present in the text.\n"
        "- synthesized_description: what THIS passage reveals about the entity.\n"
        "- raw_excerpt must be verbatim text from the passage.\n"
        "- Relationships must only use the allowed RELATION TYPES listed above.\n"
        "- Entity type must match one of the allowed ENTITY TYPES listed above.\n"
        "- If you find no entities, return empty arrays — always call the tool."
    )


def _parse_tool_result(
    raw: dict,
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    entities = [
        ExtractedEntity(
            name=e["name"],
            type=e["type"],
            aliases=e.get("aliases", []),
            attributes=e.get("attributes", {}),
            raw_excerpt=e.get("raw_excerpt", ""),
            synthesized_description=e.get("synthesized_description", ""),
        )
        for e in raw.get("entities", [])
    ]
    relationships = [
        ExtractedRelationship(
            from_entity_name=r["from_entity_name"],
            relation_type=r["relation_type"],
            to_entity_name=r["to_entity_name"],
            raw_excerpt=r.get("raw_excerpt", ""),
            synthesized_description=r.get("synthesized_description", ""),
        )
        for r in raw.get("relationships", [])
    ]
    return entities, relationships


def extract_document(text: str, domain: Domain) -> list[ChunkResult]:
    """Chunk text and extract entities/relationships via Claude. Never raises."""
    client = anthropic.Anthropic()
    system_prompt = _build_system_prompt(domain)
    chunks = _chunk_text(text)
    results: list[ChunkResult] = []

    for chunk_text, passage_index in chunks:
        try:
            response = client.messages.create(
                model=EXTRACTION_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": chunk_text}],
                tools=[EXTRACTION_TOOL],
                tool_choice={"type": "any"},
            )
            tool_block = next(
                (b for b in response.content if b.type == "tool_use"), None
            )
            if tool_block is None:
                logger.warning(
                    "No tool_use block in Claude response for passage %d", passage_index
                )
                entities, relationships = [], []
            else:
                entities, relationships = _parse_tool_result(tool_block.input)

        except Exception as exc:
            logger.error("Claude API error for passage %d: %s", passage_index, exc)
            entities, relationships = [], []

        results.append(
            ChunkResult(
                passage_index=passage_index,
                entities=entities,
                relationships=relationships,
                extraction_model=EXTRACTION_MODEL,
            )
        )

    return results
