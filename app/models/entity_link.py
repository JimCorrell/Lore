import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EntityLink(Base):
    """
    A directed relationship between two entities, sourced to a specific appearance.
    Cascades delete when the parent appearance is removed (e.g. on re-ingestion).
    Bidirectional relation types (ALLIED_WITH, OPPOSED_BY) are written as two
    rows — one in each direction — by the ingestion pipeline.
    """

    __tablename__ = "entity_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    # ON DELETE CASCADE — links are owned by their sourcing appearance
    appearance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appearances.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    synthesized_description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "from_entity_id != to_entity_id",
            name="ck_entity_links_no_self_reference",
        ),
    )
