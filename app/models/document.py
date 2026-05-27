import uuid
from datetime import date, datetime
from sqlalchemy import (
    String,
    Text,
    Float,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("domains.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # real-world publication date — drives publication order
    published_at: Mapped[date | None] = mapped_column(Date)
    # in-universe chronological position — drives chronological order
    # negative = BBY, positive = ABY, NULL = unknown or non-datable
    timeline_position: Mapped[float | None] = mapped_column(Float)
    # caller-supplied stable identifier (ISBN, comic issue ID, etc.)
    external_id: Mapped[str | None] = mapped_column(String(255))
    # Python attr is extra_metadata to avoid shadowing SQLAlchemy's Base.metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingestion_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        # pending | processing | complete | failed
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "domain_id", "external_id", name="uq_documents_domain_external"
        ),
    )
