import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Appearance(Base):
    """
    The atomic unit of knowledge. One record per entity × document passage.
    Cascades delete when the parent document is re-ingested or removed.
    """

    __tablename__ = "appearances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    # ON DELETE CASCADE — re-ingesting a document wipes and replaces its appearances
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # verbatim sentence(s) from the source that mention this entity
    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    # what this passage tells us about this entity (written by extraction model)
    synthesized_description: Mapped[str] = mapped_column(Text, nullable=False)
    # structured attributes extracted from this specific passage
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # position of the passage within the document (for chunked documents)
    passage_index: Mapped[int | None] = mapped_column(Integer)
    extraction_model: Mapped[str | None] = mapped_column(String(64))
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
