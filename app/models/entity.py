import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    aliases: Mapped[list] = mapped_column(ARRAY(Text()), nullable=False, default=list)
    # Python attr is entity_type to avoid shadowing SQLAlchemy's polymorphic `type`
    entity_type: Mapped[str] = mapped_column("type", String(64), nullable=False)
    domain_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("domains.id"), nullable=False
    )
    # merged/aggregated attributes across all appearances
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    appearance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merge_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="clean",
        # clean | auto_merged (flagged for human audit)
    )
    # entity IDs that were merged into this one
    merged_from: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
