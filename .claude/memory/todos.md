---
name: todos
description: Pending work, next steps, and phase-gated backlog for Lore
metadata:
  type: project
---

## Phase 1 — Core Ingestion Pipeline: COMPLETE (2026-05-27)

All Phase 1 work is done and tested. The full pipeline is live:
- `POST /api/v1/documents` → background extraction via Claude → entity resolution → appearances/links
- `GET /api/v1/entities` + `GET /api/v1/entities/{id}/biography`
- 40 integration tests passing

### Known Phase 1 limitations (deferred to Phase 2)

- `appearance_count` is not decremented when a document is deleted (stale but acceptable)
- Fuzzy matching only runs against `canonical_name`, not individual alias values
- Extraction model (`claude-sonnet-4-6`) and chunk sizes (1500/150 tokens) are hard-coded constants in `extraction.py`

---

## Phase 2 — MCP Server + Graph API (Next)

- MCP server exposing Lore as a tool for Claude
- Graph traversal endpoints — neighbors, subgraph by entity type
- `GET /api/v1/entities/{id}/links` — outbound relationships for an entity
- Knowledge graph export
- Move `EXTRACTION_MODEL`, `CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `FUZZY_THRESHOLD` to `Settings`
- Fix stale `appearance_count` on document delete

## Phase 3 — Human Review Layer (Planned)

- Review endpoints against `merge_events` table — list unreviewed merges, approve/reject
- `reviewed / reviewed_by / reviewed_at` fields on MergeEvent are already in the schema

## Phase 4 — Chronicle Integration + Embeddings (Planned)

- Add `vector(1024)` columns to `entities` and `appearances` (commented-out SQL already in migration 0001)
- Voyage AI embeddings for entities and appearances
- pgvector similarity search
- Chronicle integration

## Phase 5 — Semantic Search (Optional)

- Natural language search over the entity/appearance corpus using Phase 4 embeddings

## Infrastructure TODOs

- `ruff`, `pytest`, `httpx` are dev deps installed manually — not in `requirements.txt`; consider adding a `requirements-dev.txt`
- Test DB (`lore_test`) must be created manually — consider adding a `make test-db` target
- No CI/CD yet

---
## Session ended: 2026-05-27 18:22
