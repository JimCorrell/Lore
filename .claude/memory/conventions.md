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
- Business logic (when it exists) belongs in `app/services/` — no FastAPI deps allowed there
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

**Relation types** in `attribute_schema` are stored as `JSONB` in the DB but represented as `list[RelationType]` in Pydantic. When writing to the DB, always call `.model_dump()` on each `RelationType` before storing: `[rt.model_dump() for rt in body.relation_types]`.

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

## JSONB Mutation Gotcha

SQLAlchemy's `onupdate` trigger only fires on scalar column changes. JSONB field mutations (e.g. modifying `attributes` dict in-place) may not trigger `updated_at` auto-update. **Always set `updated_at` explicitly** after JSONB mutations:
```python
domain.updated_at = datetime.now(timezone.utc)
```

## Schema Separation

ORM models (`app/models/`) are pure SQLAlchemy — no Pydantic. Pydantic schemas (`app/schemas/`) are pure Pydantic — no SQLAlchemy. Response schemas use `model_config = ConfigDict(from_attributes=True)` to serialize from ORM instances.

## Logging

No `print()`. Use the `logging` module. (No logging is configured yet in Phase 1 skeleton.)

## Commit Style

Conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`, etc.).

## Anti-patterns

- Don't use `print()` — use logging
- Don't put FastAPI dependencies (`Depends`, `Request`, `Response`) inside `app/services/`
- Don't define ORM models with `sqlalchemy.url` hardcoded — always read from `settings`
- Don't use `git add .` / `git add -A` — stage files explicitly
- Don't use `--no-verify` on commits
