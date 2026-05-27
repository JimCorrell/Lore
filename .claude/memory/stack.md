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
| anthropic | >=0.40.0 | Claude API client (Phase 1 extraction) |
| tiktoken | 0.7.0 | Token counting (for chunking) |

**anthropic version note:** Pinned to `>=0.40.0` because 0.28.0 was incompatible with httpx 0.28.x (`proxies` kwarg removed). Always use a recent SDK version.

**Dev-only deps** (not in requirements.txt, install manually): `ruff`, `pytest`, `httpx`
```bash
.venv/bin/pip install ruff pytest httpx
```

**Note:** The ORM layer uses **sync SQLAlchemy** (psycopg2), not async. The CLAUDE.md says "async everywhere in FastAPI routes" but the current implementation uses sync `Session` + `get_db()` dependency.

## Python Version

`.python-version` pins the project to Python 3.12.

## Virtual Environment

`.venv` is managed manually (not uv, despite CLAUDE.md). The venv path is hardcoded into its own scripts, so if the project directory is moved or renamed, the venv breaks — recreate it with:
```bash
rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt ruff pytest httpx
```

## Database

- PostgreSQL 16+ (docker-compose uses `pgvector/pgvector:pg17` image)
- Port: **5433** (not 5432) to avoid conflicts with local Postgres installs
- Container name: `lore-postgres`
- Credentials: `lore / lore_dev / lore` (user/password/db)
- Data volume: `lore_pgdata` (persists across `docker compose down`)
- Required extensions: `pg_trgm` (created by migration 0001)
- Planned extension: `vector` (pgvector — commented out in migration 0001, Phase 4)
- Test database: `lore_test` on same host/port — must be created manually and have `pg_trgm` installed:
  ```bash
  docker exec lore-postgres psql -U lore -c "CREATE DATABASE lore_test;"
  docker exec lore-postgres psql -U lore -d lore_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
  ```

## Environment Variables (.env)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Full PostgreSQL DSN |
| `ANTHROPIC_API_KEY` | Phase 1+ | `""` | Leave blank for skeleton-only dev |
| `API_KEY` | No | `"changeme"` | Service-to-service auth header |
| `APP_ENV` | No | `"development"` | Environment label |
| `APP_VERSION` | No | `"0.1.0"` | Returned in /health response |

Config is loaded via `pydantic-settings` in `app/config.py` → `Settings` class → singleton `settings` object.

## Makefile Targets

```bash
make dev      # docker compose up -d && uvicorn --reload (foreground)
make stop     # pkill uvicorn
make restart  # stop + dev
make migrate  # alembic upgrade head
make test     # pytest tests/ -v
```

**`--reload` warning:** uvicorn's `--reload` kills background tasks when source files change. If you edit files while a document is ingesting, the background task will be killed mid-run and the document may be left in `processing` state. Use `make restart` for a clean restart between editing and testing.

## Migrations

```bash
make migrate                               # apply all pending
.venv/bin/alembic downgrade -1            # roll back one
.venv/bin/alembic current                 # check state
.venv/bin/alembic revision --autogenerate -m "describe change"  # new migration
```

**Alembic config:** `alembic.ini` has no `sqlalchemy.url` — injected at runtime from `settings.database_url` in `alembic/env.py`. All ORM models are imported via `import app.models` so autogenerate sees the full schema.

## App Entry Point

`app/main.py` — `FastAPI` instance named `app`, no-op lifespan. Database connections managed per-request via `get_db()` dependency. Background tasks open their own `SessionLocal()` session.

## Interactive Docs

`http://localhost:8000/docs` (Swagger UI) when server is running.
