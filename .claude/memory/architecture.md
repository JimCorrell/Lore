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
- No `updated_at` column — only `ingested_at`

An **Entity** is a canonical record for a named thing in a domain. Key fields:
- `canonical_name` + `aliases` (ARRAY(Text())) — the authoritative name and all known alternate forms
- `entity_type` (mapped to DB column `type`) — avoids shadowing SQLAlchemy's polymorphic `type`
- `attributes` (JSONB) — merged/aggregated attributes across all appearances
- `appearance_count` — denormalized count incremented at ingest time (not decremented on document delete — known Phase 1 limitation)
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

## Ingestion Pipeline

`POST /api/v1/documents` → background task → `ingestor.py` → `extraction.py` (Claude API, chunked) → `resolver.py` (SQL dedup) → write Appearances + EntityLinks.

**Extraction:** tiktoken `cl100k_base`, 1,500 tokens/chunk, 150-token overlap. One `claude-sonnet-4-6` call per chunk via `tool_choice={"type": "any"}`, forcing use of the `record_extractions` tool.

**Entity resolution (3-step ladder per entity name):**
1. Exact `canonical_name` match (case-insensitive)
2. Exact alias match via `= ANY(aliases)` (uses GIN index)
3. Trigram similarity ≥ 0.65 via pg_trgm `similarity()` function

Fuzzy hits set `merge_status="auto_merged"`, append the absorbed name to `aliases`, and write a `MergeEvent`. Exact hits just increment `appearance_count`. Misses create a new Entity.

**Re-ingestion:** if `external_id` already exists in the domain, delete appearances (CASCADE handles entity_links), reset status to `pending`, update metadata, re-queue. Returns 409 if currently `processing`.

## Schema Decisions

**pg_trgm extension** is created in migration 0001. Required by the entity resolver for trigram similarity matching on entity names.

**pgvector / embeddings** are stubbed but commented out in migration 0001. Phase 4 will add `vector(1024)` columns to `entities` and `appearances`.

**GIN index on entities.aliases** (`idx_entities_aliases`) — alias lookup uses `= ANY(aliases)` (NOT `@>`) to avoid PostgreSQL type cast issues between `text` and `varchar` array types.

**Bidirectional links as two rows** is a deliberate denormalization. Clients never need to query both `from_entity_id` and `to_entity_id`.

**Domain ID is a slug string** (not UUID) — `domains.id` is `String(64)`, e.g. `"star-wars"`. All other tables use `gen_random_uuid()` PKs.

**SQLAlchemy column name aliasing**: `Entity.entity_type` maps to DB column `type`. `Document.extra_metadata` maps to DB column `metadata`.

**`aliases` column is `text[]`** — ORM model uses `ARRAY(Text())` to match the migration's `postgresql.ARRAY(sa.Text())`. Using `ARRAY(String)` (varchar[]) causes `= ANY()` type mismatches with the stored `text[]`.

**ingestion_status lifecycle**: `pending → processing → complete | failed`. Background task opens its own `SessionLocal()` session — never reuses the request session.

## API Surface

All routes under `/api/v1/`:
- `GET /domains` — list all domains ordered by name
- `POST /domains` — register a new domain
- `GET /domains/{domain_id}` — get one domain
- `PATCH /domains/{domain_id}` — partial update
- `POST /documents` — register + ingest (returns immediately, extraction runs in background)
- `GET /documents` — list documents (filter: domain_id, ingestion_status, limit, offset)
- `GET /documents/{id}` — get one document (use for status polling)
- `DELETE /documents/{id}` — delete document + cascade
- `GET /entities` — list entities (filter: domain_id, entity_type, merge_status, limit, offset)
- `GET /entities/{id}` — get one entity
- `GET /entities/{id}/biography` — entity + appearances ordered by timeline_position → published_at → passage_index (all NULLS LAST)

`GET /health` — liveness check including DB connectivity

## Phase Plan

| Phase | Scope | Status |
|---|---|---|
| 1 | Core ingestion pipeline | **Complete** |
| 2 | MCP server + graph API | Planned |
| 3 | Human review layer (MergeEvent review endpoints) | Planned |
| 4 | Chronicle integration + embeddings/vector search | Planned |
| 5 | Semantic search (optional) | Optional |

## File Map

```
app/
  main.py            — FastAPI app + lifespan
  config.py          — Settings via pydantic-settings (.env)
  database.py        — Sync SQLAlchemy engine, SessionLocal, Base, get_db dependency
  models/
    domain.py        — Domain ORM model
    document.py      — Document ORM model
    entity.py        — Entity ORM model (aliases: ARRAY(Text()))
    appearance.py    — Appearance ORM model
    entity_link.py   — EntityLink ORM model
    merge_event.py   — MergeEvent ORM model (audit log)
  routers/
    health.py        — /health
    domains.py       — /api/v1/domains CRUD
    documents.py     — /api/v1/documents CRUD + ingest
    entities.py      — /api/v1/entities read-only + biography
  schemas/
    domain.py        — DomainCreate, DomainUpdate, DomainResponse
    documents.py     — DocumentCreate, DocumentResponse
    entities.py      — EntityResponse, AppearanceResponse, BiographyResponse
  services/
    extraction.py    — Claude API wrapper (chunking + tool-use extraction)
    resolver.py      — Entity dedup: exact name → exact alias → fuzzy trigram
    ingestor.py      — Orchestration: extract → resolve → write appearances/links
alembic/
  versions/
    001_initial_schema.py  — All tables, indexes, pg_trgm extension
    002_seed_domains.py    — Seeds star-wars and real-world domains
tests/
  conftest.py        — rollback-per-test fixtures, test DB (lore_test), star_wars_domain fixture
  test_documents.py  — document CRUD + ingest endpoint tests
  test_entities.py   — entity list/get/biography tests
  test_resolver.py   — resolver unit tests (real PG, no mock)
  test_ingestor.py   — full pipeline tests (mock Claude)
```
