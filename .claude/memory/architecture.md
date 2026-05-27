---
name: architecture
description: Schema, design decisions, and domain model for the Lore knowledge graph service
metadata:
  type: project
---

## What Lore is

Corpus-backed knowledge graph service. Ingests unstructured source documents (novels, scripts, articles, etc.) and uses LLM extraction to build a persistent, cross-document knowledge graph of named entities and their relationships. Entities accumulate context across the full corpus and are retrievable as canonical records, assembled biographies, or traversable graph nodes.

Primary use cases: fictional universe wikis (Star Wars canon), real-world knowledge bases, any domain where named entities appear repeatedly across many source documents.

## Domain Model

A **Domain** is the top-level namespace and extraction schema. Each domain defines:
- `entity_types` — the named-entity categories for this corpus (e.g. CHARACTER, LOCATION, FACTION)
- `relation_types` — allowed relationships between entities, each with a `bidirectional` flag
- `extraction_hints` — free-text prompt guidance for the extraction model
- `attribute_schema` — per-entity-type attribute keys to capture

Two domains are seeded by migration 0002: `star-wars` (7 entity types, 10 relation types) and `real-world` (5 entity types, 9 relation types).

A **Document** is a source text ingested into a domain. Key fields:
- `source_type` — what kind of document (novel, comic, screenplay, etc.)
- `published_at` (Date) — real-world publication date, drives publication order
- `timeline_position` (Float) — in-universe chronological position (negative=BBY, positive=ABY, NULL=unknown), drives story-order sorting
- `external_id` — caller-supplied stable ID (ISBN, comic issue ID); unique per domain
- `ingestion_status` — `pending | processing | complete | failed`
- Deleting or re-ingesting a document cascades to its Appearances (and transitively to EntityLinks)

An **Entity** is a canonical record for a named thing in a domain. Key fields:
- `canonical_name` + `aliases` (ARRAY) — the authoritative name and all known alternate forms
- `entity_type` (mapped to DB column `type`) — avoids shadowing SQLAlchemy's polymorphic `type`
- `attributes` (JSONB) — merged/aggregated attributes across all appearances
- `appearance_count` — denormalized count updated at ingest time
- `merge_status` — `clean | auto_merged`; `auto_merged` flags entities that need human review
- `merged_from` (ARRAY of UUIDs) — soft record of which entity IDs were absorbed

An **Appearance** is the atomic unit of knowledge — one record per entity × document passage. Fields:
- `raw_excerpt` — verbatim sentence(s) from the source mentioning this entity
- `synthesized_description` — what this passage tells us about this entity (LLM-written)
- `attributes` (JSONB) — structured attributes extracted from this specific passage (pre-merge)
- `passage_index` — position within the document (for chunked ingestion)
- `extraction_model` — which LLM did the extraction
- Cascade-deletes from Document (ON DELETE CASCADE on `document_id`)

An **EntityLink** is a directed relationship between two entities, sourced to a specific Appearance. Fields:
- `from_entity_id → relation_type → to_entity_id`
- `appearance_id` — source appearance (CASCADE deletes links when appearance is removed)
- `raw_excerpt` + `synthesized_description` — evidence for the relationship
- Bidirectional relation types are written as **two rows** (one per direction) by the ingestion pipeline
- CHECK constraint prevents self-referential links

A **MergeEvent** is a permanent audit log entry for automatic entity merges. Fields:
- `surviving_id` (FK to entities) — the entity that absorbed others
- `absorbed_id` (UUID, no FK) — soft reference; the absorbed entity no longer exists
- `absorbed_name` — preserved for audit since the source record is gone
- `match_method` — `exact_name | exact_alias | fuzzy`
- `match_score` — confidence of fuzzy matches
- `reviewed / reviewed_by / reviewed_at` — human review workflow (Phase 3)
- Never deleted on re-ingestion — merge history is always auditable

## Schema Decisions

**pg_trgm extension** is created in migration 0001. Required by the entity resolver for Levenshtein and trigram similarity matching on entity names.

**pgvector / embeddings** are stubbed but commented out in migration 0001. Phase 4 will add `vector(1024)` columns to `entities` and `appearances`. The `CREATE EXTENSION vector` is already written as a comment to make Phase 4 a one-line migration.

**GIN index on entities.aliases** (`idx_entities_aliases`) enables efficient `@>` containment queries to look up entities by alias.

**Bidirectional links as two rows** is a deliberate denormalization. Clients never need to query both `from_entity_id` and `to_entity_id` to find all relationships — a single `WHERE from_entity_id = ?` always returns the complete picture for directed traversal.

**Domain ID is a slug string** (not UUID) — `domains.id` is `String(64)`, e.g. `"star-wars"`. This is a stable caller-chosen key, not a generated UUID. All other tables use `gen_random_uuid()` PKs.

**SQLAlchemy column name aliasing**: `Entity.entity_type` maps to DB column `type` (avoids shadowing SQLAlchemy's polymorphic attribute). `Document.extra_metadata` maps to DB column `metadata` (avoids shadowing SQLAlchemy's `Base.metadata`).

**ingestion_status lifecycle**: Documents are created as `pending`, move to `processing` during LLM extraction, then `complete` or `failed`. Re-ingestion of an existing document deletes all its Appearances (via CASCADE) and resets the status to `pending`.

## API Surface (current)

All routes under `/api/v1/`:
- `GET /domains` — list all domains ordered by name
- `POST /domains` — register a new domain (slug ID, must not already exist)
- `GET /domains/{domain_id}` — get one domain
- `PATCH /domains/{domain_id}` — partial update (only present fields applied); updating entity_types/relation_types does not retroactively change existing extractions

`GET /health` — liveness check including DB connectivity

## Phase Plan

| Phase | Scope | Status |
|---|---|---|
| 1 | Core ingestion pipeline | In progress |
| 2 | MCP server + graph API | Planned |
| 3 | Human review layer (MergeEvent review endpoints) | Planned |
| 4 | Chronicle integration + embeddings/vector search | Planned |
| 5 | Semantic search (optional) | Optional |

## File Map

```
app/
  main.py            — FastAPI app + lifespan (no startup/shutdown logic yet)
  config.py          — Settings via pydantic-settings (.env: DATABASE_URL, ANTHROPIC_API_KEY, API_KEY)
  database.py        — Sync SQLAlchemy engine, SessionLocal, Base, get_db dependency
  models/
    domain.py        — Domain ORM model
    document.py      — Document ORM model
    entity.py        — Entity ORM model
    appearance.py    — Appearance ORM model (atomic extraction unit)
    entity_link.py   — EntityLink ORM model (directed graph edges)
    merge_event.py   — MergeEvent ORM model (audit log)
  routers/
    health.py        — /health endpoint
    domains.py       — /api/v1/domains CRUD
  schemas/
    domain.py        — DomainCreate, DomainUpdate, DomainResponse + RelationType Pydantic models
alembic/
  versions/
    001_initial_schema.py  — All tables, indexes, pg_trgm extension
    002_seed_domains.py    — Seeds star-wars and real-world domains
```

**Why:** Architecture memory for future conversations — covers schema shape, key design decisions, and phase plan so we don't re-derive them from code each time.
**How to apply:** Use when designing new features, planning migrations, or evaluating whether a proposed change is consistent with existing patterns.
