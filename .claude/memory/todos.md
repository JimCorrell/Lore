---
name: todos
description: Pending work, next steps, and phase-gated backlog for Lore
metadata:
  type: project
---

## Current Phase: Phase 1 — Core Ingestion Pipeline

Phase 1 is in progress as of 2026-05-27. The database schema and domain management API are complete. What's not yet built:

### Phase 1 remaining work

- **Document ingestion endpoint** — `POST /api/v1/documents` to register a document and kick off extraction
- **Extraction service** (`app/services/extraction.py`) — calls Claude API to extract entities and relationships from document text; writes Appearances and EntityLinks
- **Entity resolver** (`app/services/resolver.py`) — deduplicates extracted entity names against existing entities using pg_trgm (fuzzy match), writes MergeEvents for auto-merges, sets `merge_status = "auto_merged"` on fuzzy hits
- **Document status polling** — `GET /api/v1/documents/{id}` to check ingestion_status
- **Chunking logic** — tiktoken is already in requirements for this; splits long documents into passages before extraction, populates `appearance.passage_index`
- **Entity CRUD** — `GET /api/v1/entities`, `GET /api/v1/entities/{id}` (canonical record), biography assembly endpoint
- **appearance_count maintenance** — increment/decrement on Entity when Appearances are written/deleted

### Phase 2 — MCP Server + Graph API (Planned)

- MCP server exposing Lore as a tool for Claude (likely `GET /api/v1/entities/{id}/biography` and graph traversal)
- Graph traversal endpoints — neighbors, shortest path, subgraph by entity type
- Knowledge graph export (e.g. JSON-LD or custom format)

### Phase 3 — Human Review Layer (Planned)

- Review endpoints against `merge_events` table — list unreviewed merges, approve/reject
- `reviewed / reviewed_by / reviewed_at` fields on MergeEvent are already in the schema waiting for this

### Phase 4 — Chronicle Integration + Embeddings (Planned)

- Add `vector(1024)` columns to `entities` and `appearances` (already stubbed as comments in migration 0001)
- Voyage AI embeddings for entities and appearances
- pgvector similarity search
- Chronicle integration (unclear scope — likely a companion service or consumer)

### Phase 5 — Semantic Search (Optional)

- Natural language search over the entity/appearance corpus using embeddings from Phase 4

## Known Schema TODOs (from migration comments)

- pgvector extension + embedding columns: already written as commented-out SQL in `001_initial_schema.py` — Phase 4 activation is a single `alembic revision` away

## Structural TODOs

- `app/services/` directory doesn't exist yet — needs to be created for Phase 1 extraction and resolver logic
- No tests yet — `tests/` directory referenced in CLAUDE.md but doesn't exist; integration tests preferred per project conventions
- Health endpoint returns 503 on DB failure but the `/health` route currently uses sync `check_db_connection()` — fine for now

---
## Session ended: 2026-05-27 16:39

---
## Session ended: 2026-05-27 17:59

---
## Session ended: 2026-05-27 18:00
