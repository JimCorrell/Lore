import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Sub-models ────────────────────────────────────────────────────────────────


class RelationType(BaseModel):
    """A named relation type with an optional bidirectionality flag.

    Bidirectional relations (e.g. ALLIED_WITH, OPPOSED_BY) are written as two
    EntityLink rows at ingest time — one in each direction — so clients never
    have to query both directions manually.
    """

    type: str = Field(..., min_length=1, max_length=64)
    bidirectional: bool = False


# ── Request bodies ────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class DomainCreate(BaseModel):
    id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable slug identifier, e.g. 'star-wars'. Lowercase letters, numbers, and hyphens only.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    entity_types: list[str] = Field(..., min_length=1)
    relation_types: list[RelationType] = Field(default_factory=list)
    extraction_hints: str | None = None
    attribute_schema: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def id_must_be_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Domain ID must be lowercase letters, numbers, and hyphens only "
                "(e.g. 'star-wars', 'real-world')"
            )
        return v

    @field_validator("entity_types")
    @classmethod
    def entity_types_must_be_nonempty_strings(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.strip():
                raise ValueError("entity_types must not contain empty strings")
        return [item.strip().upper() for item in v]


class DomainUpdate(BaseModel):
    """All fields optional — only provided fields are applied."""

    name: str | None = Field(None, min_length=1, max_length=255)
    entity_types: list[str] | None = None
    relation_types: list[RelationType] | None = None
    extraction_hints: str | None = None
    attribute_schema: dict[str, list[str]] | None = None

    @field_validator("entity_types")
    @classmethod
    def entity_types_must_be_nonempty_strings(
        cls, v: list[str] | None
    ) -> list[str] | None:
        if v is None:
            return v
        for item in v:
            if not item.strip():
                raise ValueError("entity_types must not contain empty strings")
        return [item.strip().upper() for item in v]


# ── Response ──────────────────────────────────────────────────────────────────


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    entity_types: list[str]
    relation_types: list[Any]
    extraction_hints: str | None
    attribute_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime
