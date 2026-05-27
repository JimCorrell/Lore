import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MergeEvent(Base):
    """
    Audit log for automatic entity merges. Written whenever the entity resolver
    merges a candidate name into an existing entity via fuzzy matching.
    Retained permanently — not deleted on re-ingestion — so the merge history
    is always auditable. Phase 3 adds human review endpoints against this table.
    """

    __tablename__ = "merge_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    surviving_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    # soft reference — the absorbed entity no longer exists as a record
    absorbed_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # preserved for audit since the entity record is gone
    absorbed_name: Mapped[str] = mapped_column(String(512), nullable=False)
    match_method: Mapped[str] = mapped_column(String(32), nullable=False)
    # exact_name | exact_alias | fuzzy
    match_score: Mapped[float | None] = mapped_column(Float)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
