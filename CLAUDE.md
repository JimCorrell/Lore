# Lore

## What this is
Corpus-backed knowledge graph service. Ingests unstructured source documents and uses Claude to extract named entities, contextual descriptions, and relationships. Entities accumulate context across the full document corpus and are retrievable as canonical records, assembled biographies, or traversable knowledge graph nodes. Primary use cases: fictional universe wikis (Star Wars canon), real-world knowledge bases.

## Stack
FastAPI · PostgreSQL 16 / pgvector · Python 3.12 · SQLAlchemy (sync) · Claude API (claude-sonnet-4-6) · tiktoken · ruff · pytest

## Key paths
app/routers/       — FastAPI routers (one file per resource)
app/models/        — SQLAlchemy ORM models (one file per table)
app/schemas/       — Pydantic request/response schemas
app/services/      — business logic (no FastAPI deps)
tests/             — pytest, integration tests preferred

## Memory routing
architecture.md — schema, design decisions, domain model, ingestion pipeline, API surface
stack.md        — deps, config, env, Makefile targets, venv notes
conventions.md  — naming, patterns, anti-patterns (including array type and alias lookup rules)
todos.md        — phase status, pending work, next steps

## Constraints
- `.venv/bin/` prefix for all invocations (not uv — venv is managed manually)
- ruff format + ruff check (not black)
- sync SQLAlchemy throughout (not async) — `Session`, `get_db()`, `SessionLocal()`
- no print() — use logging module
- conventional commits
- background tasks must open their own `SessionLocal()` — never reuse the request session
- `ARRAY(Text())` for all string array columns — never `ARRAY(String)`
