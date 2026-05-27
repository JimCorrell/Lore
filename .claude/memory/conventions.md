---
name: conventions
description: Naming conventions, code patterns, and anti-patterns for the Lore codebase
metadata:
  type: project
---

## Project Layout Conventions

- One ORM model per file under `app/models/`
- One router per resource under `app/routers/`
- Pydantic request/response schemas live in `app/schemas/` (separate from ORM models)
- Business logic belongs in `app/services/` — no FastAPI deps (`Depends`, `Request`, `Response`) allowed there
- All models registered in `app/models/__init__.py` so `import app.models` in `alembic/env.py` captures the full schema for autogenerate

## Naming Patterns

**ORM models** use SQLAlchemy `Mapped` + `mapped_column` (SQLAlchemy 2.x style). All models inherit from `app.database.Base`.

**Column aliasing** — when a Python attribute name would collide with SQLAlchemy internals, pass the DB column name explicitly:
```python
entity_type: Mapped[str] = mapped_column("type", ...)       # avoids polymorphic `type`
extra_metadata: Mapped[dict] = mapped_column("metadata", ...)  # avoids Base.metadata
```

**Router helpers** named `_get_or_404(id, db)` — private convention for DRY 404 logic per router.

**Domain IDs** are lowercase slugs (`star-wars`, `real-world`) validated by `_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` in `DomainCreate`.

**Entity types** are stored UPPERCASE — `DomainCreate` and `DomainUpdate` validators call `.strip().upper()` on all values.

**Relation types** in `relation_types` are stored as JSONB in the DB but represented as `list[RelationType]` in Pydantic. When writing to the DB, always call `.model_dump()` on each `RelationType`: `[rt.model_dump() for rt in body.relation_types]`.

## Array Column Type: Always `ARRAY(Text())`

The `aliases` column on Entity (and any future array-of-strings columns) must use `ARRAY(Text())`, NOT `ARRAY(String)`. Reason: the migration creates `text[]` columns; using `ARRAY(String)` in the ORM creates `varchar[]` which causes type mismatch errors in array queries. Keep ORM and migration in sync.

## Alias Lookup: Use `= ANY()` Not `@>`

```python
# CORRECT — works regardless of text[] vs varchar[] mismatch
text("SELECT id FROM entities WHERE domain_id = :d AND :name = ANY(aliases)")

# WRONG — type cast required, fragile across ORM/migration differences
text("SELECT id FROM entities WHERE domain_id = :d AND aliases @> ARRAY[:name]::text[]")
```

## Status Enums (strings, not Python enums)

| Field | Values |
|---|---|
| `Document.ingestion_status` | `pending \| processing \| complete \| failed` |
| `Entity.merge_status` | `clean \| auto_merged` |
| `MergeEvent.match_method` | `exact_name \| exact_alias \| fuzzy` |

These are stored as `String(32)` — no DB enum type, no Python `Enum` class. Keep as bare string literals.

## Cascade Rules

- `appearances.document_id` → ON DELETE CASCADE (re-ingesting a document wipes its appearances)
- `entity_links.appearance_id` → ON DELETE CASCADE (links are owned by their sourcing appearance)
- `merge_events` → **no cascade** — audit log is permanent, never deleted on re-ingestion

## Bidirectional Relationships

Bidirectional `relation_types` (e.g. `ALLIED_WITH`, `OPPOSED_BY`) are written as **two EntityLink rows** at ingest time — one in each direction. This is intentional denormalization so clients can always query by `from_entity_id` only and get the complete picture.

## JSONB / ARRAY Mutation Gotcha

SQLAlchemy's `onupdate` trigger and dirty-tracking only fire on scalar column changes. Mutating a JSONB dict or ARRAY list in-place is invisible to SQLAlchemy. Always:
1. Assign a new object: `entity.aliases = entity.aliases + [new_alias]`
2. Set `updated_at` explicitly: `entity.updated_at = datetime.now(timezone.utc)`
3. Call `db.flush()` to push to DB (especially with `autoflush=False` sessions)

## Background Tasks: Own Session

Background tasks (FastAPI `BackgroundTasks`) run after the response is sent. The request's `db` session is closed by then. Always open a fresh session in background tasks:
```python
def _run_ingestion(doc_id: UUID, text: str) -> None:
    db = SessionLocal()
    try:
        ingest_document(doc_id, text, db)
    finally:
        db.close()
```
Never pass the request session into a background task.

## Test Session: autoflush=False

The test session is created with `autoflush=False`. After writing objects with `db.add()`, call `db.flush()` explicitly before querying them — otherwise queries return stale data. This applies to service code that needs to be visible within the same session.

## Schema Separation

ORM models (`app/models/`) are pure SQLAlchemy — no Pydantic. Pydantic schemas (`app/schemas/`) are pure Pydantic — no SQLAlchemy. Response schemas use `model_config = ConfigDict(from_attributes=True)` to serialize from ORM instances.

## Logging

No `print()`. Use the `logging` module with a module-level logger:
```python
logger = logging.getLogger(__name__)
```

## Commit Style

Conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`, etc.).

## Anti-patterns

- Don't use `print()` — use logging
- Don't put FastAPI dependencies inside `app/services/`
- Don't use `ARRAY(String)` for string arrays — use `ARRAY(Text())` to match migrations
- Don't use `@>` for alias array containment — use `= ANY()`
- Don't pass the request `db` session to background tasks — open a new `SessionLocal()`
- Don't edit source files while a document is ingesting with `--reload` active — kills the background task
- Don't use `git add .` / `git add -A` — stage files explicitly
- Don't use `--no-verify` on commits
