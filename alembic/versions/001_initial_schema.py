"""Initial schema — all tables, indexes, and extensions.

Revision ID: 0001
Revises: —
Create Date: 2026-05-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm provides Levenshtein and trigram functions used by the entity resolver
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── domains ──────────────────────────────────────────────────────────────
    op.create_table(
        "domains",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_types", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("relation_types", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("extraction_hints", sa.Text()),
        sa.Column("attribute_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "domain_id",
            sa.String(64),
            sa.ForeignKey("domains.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(255)),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("published_at", sa.Date()),
        sa.Column("timeline_position", sa.Float()),
        sa.Column("external_id", sa.String(255)),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "ingestion_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ingestion_error", sa.Text()),
        sa.UniqueConstraint(
            "domain_id", "external_id", name="uq_documents_domain_external"
        ),
    )
    op.create_index("idx_documents_domain", "documents", ["domain_id"])
    op.create_index("idx_documents_status", "documents", ["ingestion_status"])
    op.create_index("idx_documents_published", "documents", ["published_at"])
    op.create_index("idx_documents_timeline", "documents", ["timeline_position"])

    # ── entities ──────────────────────────────────────────────────────────────
    op.create_table(
        "entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column(
            "domain_id",
            sa.String(64),
            sa.ForeignKey("domains.id"),
            nullable=False,
        ),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "appearance_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "merge_status",
            sa.String(32),
            nullable=False,
            server_default="clean",
        ),
        sa.Column(
            "merged_from",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_entities_domain", "entities", ["domain_id"])
    op.create_index("idx_entities_type", "entities", ["type"])
    op.create_index("idx_entities_canonical", "entities", ["canonical_name"])
    op.create_index("idx_entities_merge_status", "entities", ["merge_status"])
    # GIN index for efficient containment queries on the aliases array
    op.create_index(
        "idx_entities_aliases",
        "entities",
        ["aliases"],
        postgresql_using="gin",
    )

    # ── appearances ───────────────────────────────────────────────────────────
    op.create_table(
        "appearances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_excerpt", sa.Text(), nullable=False),
        sa.Column("synthesized_description", sa.Text(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("passage_index", sa.Integer()),
        sa.Column("extraction_model", sa.String(64)),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_appearances_entity", "appearances", ["entity_id"])
    op.create_index("idx_appearances_document", "appearances", ["document_id"])
    op.create_index(
        "idx_appearances_entity_document",
        "appearances",
        ["entity_id", "document_id"],
    )

    # ── entity_links ──────────────────────────────────────────────────────────
    op.create_table(
        "entity_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "from_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column(
            "to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        sa.Column(
            "appearance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appearances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_excerpt", sa.Text(), nullable=False),
        sa.Column("synthesized_description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_entity_id != to_entity_id",
            name="ck_entity_links_no_self_reference",
        ),
    )
    op.create_index("idx_links_from", "entity_links", ["from_entity_id"])
    op.create_index("idx_links_to", "entity_links", ["to_entity_id"])
    op.create_index("idx_links_appearance", "entity_links", ["appearance_id"])
    op.create_index("idx_links_relation", "entity_links", ["relation_type"])

    # ── merge_events ──────────────────────────────────────────────────────────
    op.create_table(
        "merge_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "surviving_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        # soft reference — absorbed entity no longer exists as a record
        sa.Column("absorbed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("absorbed_name", sa.String(512), nullable=False),
        sa.Column("match_method", sa.String(32), nullable=False),
        sa.Column("match_score", sa.Float()),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_merge_events_surviving", "merge_events", ["surviving_id"])
    op.create_index("idx_merge_events_reviewed", "merge_events", ["reviewed"])

    # Phase 4 — semantic search (uncomment when ready):
    # op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # op.add_column("entities", sa.Column("embedding", vector(1024)))
    # op.add_column("appearances", sa.Column("embedding", vector(1024)))


def downgrade() -> None:
    op.drop_table("merge_events")
    op.drop_table("entity_links")
    op.drop_table("appearances")
    op.drop_table("entities")
    op.drop_table("documents")
    op.drop_table("domains")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
