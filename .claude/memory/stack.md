---
name: stack
description: Dependencies, configuration, environment variables, and dev tooling for Lore
metadata:
  type: project
---

## Runtime Dependencies (requirements.txt)

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.111.0 | Web framework |
| uvicorn[standard] | 0.29.0 | ASGI server |
| sqlalchemy | 2.0.30 | ORM + Core (sync) |
| alembic | 1.13.1 | Database migrations |
| psycopg2-binary | 2.9.10 | PostgreSQL driver (sync) |
| pydantic | 2.7.1 | Data validation / schemas |
| pydantic-settings | 2.2.1 | `.env`-backed settings |
| python-dotenv | 1.0.1 | `.env` file loading |
| anthropic | 0.28.0 | Claude API client (Phase 1 extraction) |
| tiktoken | 0.7.0 | Token counting (for chunking) |

**Note:** The ORM layer uses **sync SQLAlchemy** (psycopg2), not async. The CLAUDE.md says "async everywhere in FastAPI routes" but the current implementation uses sync `Session` + `get_db()` dependency. This is the current state; async migration may come in a later phase.

## Python Version

`.python-version` pins the project to Python 3.12.

## Database

- PostgreSQL 16+ (docker-compose uses `pgvector/pgvector:pg17` image)
- Port: **5433** (not 5432) to avoid conflicts with local Postgres installs
- Container name: `lore-postgres`
- Credentials: `lore / lore_dev / lore` (user/password/db)
- Data volume: `lore_pgdata` (persists across `docker compose down`)
- Required extensions: `pg_trgm` (trigram/Levenshtein for entity resolver — created by migration 0001)
- Planned extension: `vector` (pgvector for semantic search — commented out in migration 0001, Phase 4)

## Environment Variables (.env)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Full PostgreSQL DSN |
| `ANTHROPIC_API_KEY` | Phase 1+ | `""` | Leave blank for skeleton-only dev |
| `API_KEY` | No | `"changeme"` | Service-to-service auth header |
| `APP_ENV` | No | `"development"` | Environment label |
| `APP_VERSION` | No | `"0.1.0"` | Returned in /health response |

Config is loaded via `pydantic-settings` in `app/config.py` → `Settings` class → singleton `settings` object.

## Dev Tooling

**Start dev environment:**
```bash
make dev
# equivalent to: docker compose up -d && .venv/bin/uvicorn app.main:app --reload
```

**Migrations:**
```bash
alembic upgrade head          # apply all pending
alembic downgrade -1          # roll back one
alembic current               # check state
alembic revision --autogenerate -m "describe change"  # new migration
```

**Alembic config:** `alembic.ini` has no `sqlalchemy.url` — the URL is injected at runtime from `settings.database_url` in `alembic/env.py`. All ORM models are imported via `import app.models` (the `__init__.py` imports all six models) so Alembic's autogenerate sees the full schema.

**Linting/formatting:** ruff (not black). CLAUDE.md: `ruff format + ruff check`.

**Invocation:** CLAUDE.md specifies `uv run` for all invocations, but the Makefile uses `.venv/bin/uvicorn` directly. The `.venv` is managed manually (or via uv).

## App Entry Point

`app/main.py` — `FastAPI` instance named `app`, with a no-op lifespan context. Database connections are managed per-request via `get_db()` dependency (no connection pool held across requests beyond SQLAlchemy's pool).

## Interactive Docs

`http://localhost:8000/docs` (Swagger UI) when server is running.
