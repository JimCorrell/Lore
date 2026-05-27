import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.appearance import Appearance
from app.models.document import Document
from app.models.domain import Domain
from app.schemas.documents import DocumentCreate, DocumentResponse
from app.services.ingestor import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _get_or_404(doc_id: uuid.UUID, db: Session) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )
    return doc


def _run_ingestion(doc_id: uuid.UUID, text: str) -> None:
    db = SessionLocal()
    try:
        ingest_document(doc_id, text, db)
    except Exception as exc:
        logger.error("Unhandled error in background ingest for %s: %s", doc_id, exc)
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document",
)
def create_document(
    body: DocumentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Document:
    """
    Register a source document and kick off entity extraction in the background.
    Returns immediately with `ingestion_status: "pending"`. Poll `GET /{id}` to
    check progress. If `external_id` is provided and a document with the same
    `(domain_id, external_id)` already exists, it will be re-ingested (unless
    it is currently processing, which returns 409).
    """
    domain = db.get(Domain, body.domain_id)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{body.domain_id}' not found.",
        )

    doc: Document | None = None

    if body.external_id is not None:
        doc = (
            db.query(Document)
            .filter_by(domain_id=body.domain_id, external_id=body.external_id)
            .first()
        )
        if doc is not None:
            if doc.ingestion_status == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Document '{body.external_id}' is currently being ingested.",
                )
            # Delete existing appearances — CASCADE handles entity_links
            db.query(Appearance).filter_by(document_id=doc.id).delete()
            doc.title = body.title
            doc.author = body.author
            doc.source_type = body.source_type
            doc.published_at = body.published_at
            doc.timeline_position = body.timeline_position
            doc.extra_metadata = body.extra_metadata
            doc.ingestion_status = "pending"
            doc.ingestion_error = None
            db.commit()
            db.refresh(doc)

    if doc is None:
        doc = Document(
            domain_id=body.domain_id,
            title=body.title,
            author=body.author,
            source_type=body.source_type,
            published_at=body.published_at,
            timeline_position=body.timeline_position,
            external_id=body.external_id,
            extra_metadata=body.extra_metadata,
            ingestion_status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

    background_tasks.add_task(_run_ingestion, doc.id, body.text)
    return doc


@router.get("", response_model=list[DocumentResponse], summary="List documents")
def list_documents(
    domain_id: str | None = None,
    ingestion_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[Document]:
    q = db.query(Document)
    if domain_id:
        q = q.filter(Document.domain_id == domain_id)
    if ingestion_status:
        q = q.filter(Document.ingestion_status == ingestion_status)
    return q.order_by(Document.ingested_at.desc()).offset(offset).limit(limit).all()


@router.get("/{doc_id}", response_model=DocumentResponse, summary="Get a document")
def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)) -> Document:
    return _get_or_404(doc_id, db)


@router.delete(
    "/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a document"
)
def delete_document(doc_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """
    Delete a document and its appearances. Entity links cascade from appearances.
    Note: entity.appearance_count is not decremented on delete — accepted Phase 1 limitation.
    """
    doc = _get_or_404(doc_id, db)
    db.delete(doc)
    db.commit()
