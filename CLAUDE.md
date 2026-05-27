# [Project Name]

## What this is
[One paragraph. What problem does this solve? Who uses it?]

## Stack
FastAPI · PostgreSQL 16 / pgvector · Python 3.12 · uv · Voyage AI · Claude API

## Key paths
src/api/       — FastAPI routers
src/models/    — Pydantic + SQLModel models
src/db/        — asyncpg sessions, migrations
src/services/  — business logic (no FastAPI deps)
tests/         — pytest, integration tests preferred

## Memory routing
architecture.md — schema, design decisions, domain model
stack.md        — deps, config, env, pyproject
conventions.md  — naming, patterns, anti-patterns
todos.md        — pending work, next steps

## Constraints
- uv run for all invocations
- ruff format + ruff check (not black)
- async everywhere in FastAPI routes
- no print() — use logging module
- conventional commits
