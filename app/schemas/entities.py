import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name: str
    aliases: list[str]
    entity_type: str
    domain_id: str
    attributes: dict[str, Any]
    appearance_count: int
    merge_status: str
    merged_from: list[uuid.UUID] | None
    created_at: datetime
    updated_at: datetime


class AppearanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    document_id: uuid.UUID
    raw_excerpt: str
    synthesized_description: str
    attributes: dict[str, Any]
    passage_index: int | None
    extraction_model: str | None
    extracted_at: datetime


class BiographyResponse(BaseModel):
    entity: EntityResponse
    appearances: list[AppearanceResponse]
