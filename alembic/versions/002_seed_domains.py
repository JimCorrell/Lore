"""Seed built-in domains — star-wars and real-world.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Domain definitions ────────────────────────────────────────────────────────

STAR_WARS = {
    "id": "star-wars",
    "name": "Star Wars Canon",
    "entity_types": [
        "CHARACTER", "LOCATION", "FACTION", "SHIP", "ARTIFACT", "SPECIES", "EVENT",
    ],
    "relation_types": [
        {"type": "COMMANDS",        "bidirectional": False},
        {"type": "SERVES_UNDER",    "bidirectional": False},
        {"type": "MEMBER_OF",       "bidirectional": False},
        {"type": "ALLIED_WITH",     "bidirectional": True},
        {"type": "OPPOSED_BY",      "bidirectional": True},
        {"type": "LOCATED_IN",      "bidirectional": False},
        {"type": "PARTICIPATES_IN", "bidirectional": False},
        {"type": "OWNS",            "bidirectional": False},
        {"type": "CREWED_BY",       "bidirectional": False},
        {"type": "DESTROYED_BY",    "bidirectional": False},
    ],
    "extraction_hints": (
        "Extract named entities from Star Wars canon source material. "
        "Characters include all named individuals — Jedi, Sith, clones, droids, "
        "aliens, Imperial officers, rebels. "
        "Locations include planets, moons, space stations, star systems, and named regions. "
        "Factions include political bodies, military organizations, and criminal enterprises. "
        "Ships include all named vessels. "
        "Artifacts include weapons, holocrons, and named objects of significance. "
        "Species includes named alien races. "
        "Events include named battles, treaties, and historical occurrences."
    ),
    "attribute_schema": {
        "CHARACTER": ["species", "affiliation", "era", "homeworld", "force_sensitive", "rank", "titles"],
        "LOCATION":  ["region", "type", "climate", "galactic_zone", "controlling_faction"],
        "FACTION":   ["era", "political_alignment", "leader", "headquarters"],
        "SHIP":      ["class", "affiliation", "captain", "fleet"],
        "ARTIFACT":  ["force_sensitive", "current_owner", "origin"],
        "SPECIES":   ["homeworld", "force_sensitivity", "average_lifespan"],
        "EVENT":     ["era", "location", "participants", "outcome"],
    },
}

REAL_WORLD = {
    "id": "real-world",
    "name": "Real World",
    "entity_types": ["PERSON", "PLACE", "ORGANIZATION", "CONCEPT", "EVENT"],
    "relation_types": [
        {"type": "WORKS_FOR",       "bidirectional": False},
        {"type": "FOUNDED",         "bidirectional": False},
        {"type": "LOCATED_IN",      "bidirectional": False},
        {"type": "PART_OF",         "bidirectional": False},
        {"type": "ALLIED_WITH",     "bidirectional": True},
        {"type": "OPPOSED_BY",      "bidirectional": True},
        {"type": "PARTICIPATES_IN", "bidirectional": False},
        {"type": "LEADS",           "bidirectional": False},
        {"type": "CREATED",         "bidirectional": False},
    ],
    "extraction_hints": (
        "Extract real-world named entities. "
        "Persons are named individuals. "
        "Places are geographic locations, countries, cities, buildings. "
        "Organizations include companies, governments, and institutions. "
        "Concepts include named theories, doctrines, movements, and frameworks. "
        "Events include named historical occurrences, conferences, and incidents."
    ),
    "attribute_schema": {
        "PERSON":       ["role", "nationality", "affiliation", "birth_year", "death_year"],
        "PLACE":        ["country", "type", "coordinates"],
        "ORGANIZATION": ["type", "founded", "headquarters"],
        "CONCEPT":      ["domain", "origin"],
        "EVENT":        ["date", "location", "participants", "outcome"],
    },
}

DOMAINS = [STAR_WARS, REAL_WORLD]

# ── Migration ─────────────────────────────────────────────────────────────────

INSERT_DOMAIN = sa.text("""
    INSERT INTO domains (id, name, entity_types, relation_types, extraction_hints, attribute_schema)
    VALUES (
        :id,
        :name,
        CAST(:entity_types AS jsonb),
        CAST(:relation_types AS jsonb),
        :extraction_hints,
        CAST(:attribute_schema AS jsonb)
    )
    ON CONFLICT (id) DO NOTHING
""")


def upgrade() -> None:
    conn = op.get_bind()
    for domain in DOMAINS:
        conn.execute(
            INSERT_DOMAIN,
            {
                "id":               domain["id"],
                "name":             domain["name"],
                "entity_types":     json.dumps(domain["entity_types"]),
                "relation_types":   json.dumps(domain["relation_types"]),
                "extraction_hints": domain["extraction_hints"],
                "attribute_schema": json.dumps(domain["attribute_schema"]),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM domains WHERE id IN ('star-wars', 'real-world')")
    )
