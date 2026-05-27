from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Domain
from app.schemas.domain import DomainCreate, DomainResponse, DomainUpdate

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


def _get_or_404(domain_id: str, db: Session) -> Domain:
    domain = db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain_id}' not found.",
        )
    return domain


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[DomainResponse], summary="List all domains")
def list_domains(db: Session = Depends(get_db)) -> list[Domain]:
    """Return all registered domains ordered by name."""
    return db.query(Domain).order_by(Domain.name).all()


@router.post(
    "",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new domain",
)
def create_domain(body: DomainCreate, db: Session = Depends(get_db)) -> Domain:
    """
    Register a new extraction domain. The `id` must be unique and slug-formatted
    (e.g. `star-wars`). Built-in domains (`star-wars`, `real-world`) are seeded
    by migration and cannot be re-registered.
    """
    if db.get(Domain, body.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Domain '{body.id}' already exists.",
        )

    domain = Domain(
        id=body.id,
        name=body.name,
        entity_types=body.entity_types,
        relation_types=[rt.model_dump() for rt in body.relation_types],
        extraction_hints=body.extraction_hints,
        attribute_schema=body.attribute_schema,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get(
    "/{domain_id}",
    response_model=DomainResponse,
    summary="Get a domain by ID",
)
def get_domain(domain_id: str, db: Session = Depends(get_db)) -> Domain:
    """Return a single domain record including its full extraction schema."""
    return _get_or_404(domain_id, db)


@router.patch(
    "/{domain_id}",
    response_model=DomainResponse,
    summary="Update a domain",
)
def update_domain(
    domain_id: str, body: DomainUpdate, db: Session = Depends(get_db)
) -> Domain:
    """
    Partially update a domain. Only fields present in the request body are
    applied — omitted fields are left unchanged.

    Note: updating `entity_types` or `relation_types` on a domain that already
    has ingested documents does not retroactively change existing extraction
    results. Changes take effect on the next ingestion.
    """
    domain = _get_or_404(domain_id, db)

    # Apply only the fields the caller explicitly provided
    updates = body.model_dump(exclude_unset=True)

    if "name" in updates:
        domain.name = updates["name"]
    if "entity_types" in updates:
        domain.entity_types = updates["entity_types"]
    if "relation_types" in updates:
        domain.relation_types = [rt.model_dump() for rt in body.relation_types]
    if "extraction_hints" in updates:
        domain.extraction_hints = updates["extraction_hints"]
    if "attribute_schema" in updates:
        domain.attribute_schema = updates["attribute_schema"]

    # SQLAlchemy's onupdate only fires on column-level changes to scalar types;
    # JSONB mutations may not trigger it — set updated_at explicitly.
    domain.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(domain)
    return domain
