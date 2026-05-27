import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.merge_event import MergeEvent
from app.services.extraction import ExtractedEntity

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.65

_EXACT_NAME_SQL = text("""
    SELECT id FROM entities
    WHERE domain_id = :domain_id AND lower(canonical_name) = lower(:name)
    LIMIT 1
""")

_EXACT_ALIAS_SQL = text("""
    SELECT id FROM entities
    WHERE domain_id = :domain_id AND aliases @> ARRAY[:name]::varchar[]
    LIMIT 1
""")

_FUZZY_SQL = text("""
    SELECT id, canonical_name, similarity(canonical_name, :name) AS score
    FROM entities
    WHERE domain_id = :domain_id AND similarity(canonical_name, :name) >= :threshold
    ORDER BY score DESC
    LIMIT 1
""")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _exact_name_lookup(name: str, domain_id: str, db: Session) -> uuid.UUID | None:
    row = db.execute(_EXACT_NAME_SQL, {"domain_id": domain_id, "name": name}).fetchone()
    return row[0] if row else None


def _exact_alias_lookup(name: str, domain_id: str, db: Session) -> uuid.UUID | None:
    row = db.execute(
        _EXACT_ALIAS_SQL, {"domain_id": domain_id, "name": name}
    ).fetchone()
    return row[0] if row else None


def _fuzzy_lookup(
    name: str, domain_id: str, db: Session
) -> tuple[uuid.UUID, str, float] | None:
    row = db.execute(
        _FUZZY_SQL, {"domain_id": domain_id, "name": name, "threshold": FUZZY_THRESHOLD}
    ).fetchone()
    if row:
        return row[0], row[1], float(row[2])
    return None


def resolve_entities(
    entities: list[ExtractedEntity],
    domain_id: str,
    valid_entity_types: list[str],
    db: Session,
) -> dict[str, uuid.UUID]:
    """Resolve extracted entity names to entity UUIDs, creating new entities as needed."""
    name_to_id: dict[str, uuid.UUID] = {}

    for extracted in entities:
        if extracted.name in name_to_id:
            continue

        entity_type = extracted.type.upper()
        if entity_type not in valid_entity_types:
            logger.warning(
                "Extracted entity type %r not in domain entity_types — skipping %r",
                entity_type,
                extracted.name,
            )
            continue

        entity_id = _exact_name_lookup(extracted.name, domain_id, db)
        if entity_id:
            _update_existing(entity_id, extracted, match_method="exact_name", db=db)
            name_to_id[extracted.name] = entity_id
            continue

        entity_id = _exact_alias_lookup(extracted.name, domain_id, db)
        if entity_id:
            _update_existing(entity_id, extracted, match_method="exact_alias", db=db)
            name_to_id[extracted.name] = entity_id
            continue

        fuzzy = _fuzzy_lookup(extracted.name, domain_id, db)
        if fuzzy:
            entity_id, surviving_name, score = fuzzy
            logger.warning(
                "Fuzzy merge: %r → %r (score=%.3f)",
                extracted.name,
                surviving_name,
                score,
            )
            _update_existing(
                entity_id, extracted, match_method="fuzzy", score=score, db=db
            )
            _write_merge_event(
                surviving_id=entity_id,
                absorbed_name=extracted.name,
                match_method="fuzzy",
                score=score,
                db=db,
            )
            name_to_id[extracted.name] = entity_id
            continue

        entity = Entity(
            canonical_name=extracted.name,
            entity_type=entity_type,
            aliases=extracted.aliases,
            attributes=extracted.attributes,
            domain_id=domain_id,
            appearance_count=1,
        )
        db.add(entity)
        db.flush()
        name_to_id[extracted.name] = entity.id

    return name_to_id


def _update_existing(
    entity_id: uuid.UUID,
    extracted: ExtractedEntity,
    match_method: str,
    score: float | None = None,
    db: Session = None,
) -> None:
    entity = db.get(Entity, entity_id)
    if entity is None:
        return
    entity.appearance_count += 1
    new_aliases = [a for a in extracted.aliases if a not in entity.aliases]
    if new_aliases:
        entity.aliases = entity.aliases + new_aliases
    if match_method == "fuzzy" and extracted.name not in entity.aliases:
        entity.aliases = entity.aliases + [extracted.name]
        entity.merge_status = "auto_merged"
    entity.updated_at = _now()
    db.flush()


def _write_merge_event(
    surviving_id: uuid.UUID,
    absorbed_name: str,
    match_method: str,
    score: float | None,
    db: Session,
) -> None:
    event = MergeEvent(
        surviving_id=surviving_id,
        absorbed_id=uuid.uuid4(),
        absorbed_name=absorbed_name,
        match_method=match_method,
        match_score=score,
        reviewed=False,
    )
    db.add(event)
    db.flush()
