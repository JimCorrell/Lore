import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    domain_id: str
    title: str = Field(..., max_length=512)
    author: str | None = None
    source_type: str = Field(..., max_length=64)
    published_at: date | None = None
    timeline_position: float | None = None
    external_id: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    text: str  # consumed by extraction pipeline, not stored in the Document row


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain_id: str
    title: str
    author: str | None
    source_type: str
    published_at: date | None
    timeline_position: float | None
    external_id: str | None
    extra_metadata: dict[str, Any]
    ingested_at: datetime
    ingestion_status: str
    ingestion_error: str | None
