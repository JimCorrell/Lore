from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    relation_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [{ "type": "COMMANDS", "bidirectional": false }, ...]
    extraction_hints: Mapped[str | None] = mapped_column(Text)
    attribute_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
