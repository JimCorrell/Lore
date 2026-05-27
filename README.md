# Lore

Corpus-backed knowledge graph service. Ingests unstructured source documents
and extracts named entities, contextual descriptions, and relationships.
Entities accumulate context across the full document corpus and are retrievable
as canonical records, assembled biographies, or traversable knowledge graph nodes.

## Requirements

- Python 3.11+
- PostgreSQL 16 with `pg_trgm` extension (included in most distributions)

## Setup

```bash
# 1. Clone and create a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and API_KEY at minimum

# 4. Run migrations (creates all tables and seeds built-in domains)
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload
```

## Verify

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "lore",
  "version": "0.1.0",
  "environment": "development",
  "database": "ok"
}
```

## API docs

Interactive docs available at `http://localhost:8000/docs` once the server is running.

## Project structure

```
app/
  main.py           — FastAPI app + lifespan
  config.py         — Settings (loaded from .env)
  database.py       — SQLAlchemy engine, session, Base
  models/           — ORM models (one file per table)
  routers/          — FastAPI routers (one file per resource)
alembic/
  env.py            — Alembic environment (reads DB URL from app config)
  versions/         — Migration files
    001_initial_schema.py   — All tables and indexes
    002_seed_domains.py     — Built-in star-wars and real-world domains
```

## Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Check current state
alembic current

# Generate a new migration (after changing models)
alembic revision --autogenerate -m "describe the change"
```

## Phase plan

| Phase | Scope | Status |
|---|---|---|
| 1 | Core ingestion pipeline | 🔵 In progress |
| 2 | MCP server + graph API | ⬜ Planned |
| 3 | Human review layer | ⬜ Planned |
| 4 | Chronicle integration | ⬜ Planned |
| 5 | Semantic search | ⬜ Optional |
