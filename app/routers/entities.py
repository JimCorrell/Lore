import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appearance import Appearance
from app.models.document import Document
from app.models.entity import Entity
from app.schemas.entities import BiographyResponse, EntityResponse

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


def _get_or_404(entity_id: uuid.UUID, db: Session) -> Entity:
    entity = db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{entity_id}' not found.",
        )
    return entity


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[EntityResponse], summary="List entities")
def list_entities(
    domain_id: str | None = None,
    entity_type: str | None = None,
    merge_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[Entity]:
    q = db.query(Entity)
    if domain_id:
        q = q.filter(Entity.domain_id == domain_id)
    if entity_type:
        q = q.filter(Entity.entity_type == entity_type.upper())
    if merge_status:
        q = q.filter(Entity.merge_status == merge_status)
    return q.order_by(Entity.canonical_name).offset(offset).limit(limit).all()


@router.get("/{entity_id}", response_model=EntityResponse, summary="Get an entity")
def get_entity(entity_id: uuid.UUID, db: Session = Depends(get_db)) -> Entity:
    return _get_or_404(entity_id, db)


@router.get(
    "/{entity_id}/biography",
    response_model=BiographyResponse,
    summary="Get an entity's assembled biography",
)
def get_biography(
    entity_id: uuid.UUID, db: Session = Depends(get_db)
) -> BiographyResponse:
    """
    Return the entity plus all its appearances ordered chronologically:
    timeline_position → published_at → passage_index (all NULLS LAST).
    """
    entity = _get_or_404(entity_id, db)

    appearances = (
        db.query(Appearance)
        .join(Document, Appearance.document_id == Document.id)
        .filter(Appearance.entity_id == entity_id)
        .order_by(
            asc(Document.timeline_position).nulls_last(),
            asc(Document.published_at).nulls_last(),
            asc(Appearance.passage_index).nulls_last(),
        )
        .all()
    )

    return BiographyResponse(entity=entity, appearances=appearances)
