import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.appearance import Appearance
from app.models.document import Document
from app.models.domain import Domain
from app.models.entity_link import EntityLink
from app.services.extraction import ChunkResult, extract_document
from app.services.resolver import resolve_entities

logger = logging.getLogger(__name__)


def ingest_document(doc_id: uuid.UUID, text: str, db: Session) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        logger.error("ingest_document called with unknown doc_id=%s", doc_id)
        return

    doc.ingestion_status = "processing"
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()

    domain = db.get(Domain, doc.domain_id)
    if domain is None:
        _fail(doc, f"Domain '{doc.domain_id}' not found", db)
        return

    logger.info("Starting ingestion for document %s (%s)", doc_id, doc.title)

    try:
        chunk_results = extract_document(text, domain)
    except Exception as exc:
        logger.error("Extraction failed for document %s: %s", doc_id, exc)
        _fail(doc, str(exc), db)
        return

    valid_types = [t.upper() for t in domain.entity_types]
    valid_relation_types = {rt["type"] for rt in domain.relation_types}
    bidir_types = {
        rt["type"] for rt in domain.relation_types if rt.get("bidirectional")
    }

    total_entities = sum(len(c.entities) for c in chunk_results)
    logger.info(
        "Extraction complete for %s: %d chunks, %d entities total",
        doc_id,
        len(chunk_results),
        total_entities,
    )

    try:
        for chunk in chunk_results:
            _process_chunk(
                chunk=chunk,
                doc_id=doc_id,
                domain_id=doc.domain_id,
                valid_types=valid_types,
                valid_relation_types=valid_relation_types,
                bidir_types=bidir_types,
                db=db,
            )
        db.commit()
    except Exception as exc:
        logger.error("Write failed for document %s: %s", doc_id, exc)
        db.rollback()
        _fail(doc, str(exc), db)
        return

    doc.ingestion_status = "complete"
    doc.ingestion_error = None
    db.commit()
    logger.info("Ingestion complete for document %s", doc_id)


def _process_chunk(
    chunk: ChunkResult,
    doc_id: uuid.UUID,
    domain_id: str,
    valid_types: list[str],
    valid_relation_types: set[str],
    bidir_types: set[str],
    db: Session,
) -> None:
    if not chunk.entities:
        return

    name_to_id = resolve_entities(chunk.entities, domain_id, valid_types, db)

    # Track appearances by entity name so relationship links have an appearance_id
    chunk_appearances: dict[str, Appearance] = {}
    seen_entity_ids: set[uuid.UUID] = set()

    for extracted in chunk.entities:
        entity_id = name_to_id.get(extracted.name)
        if entity_id is None:
            continue
        if entity_id in seen_entity_ids:
            continue
        seen_entity_ids.add(entity_id)

        appearance = Appearance(
            entity_id=entity_id,
            document_id=doc_id,
            raw_excerpt=extracted.raw_excerpt,
            synthesized_description=extracted.synthesized_description,
            attributes=extracted.attributes,
            passage_index=chunk.passage_index,
            extraction_model=chunk.extraction_model,
        )
        db.add(appearance)
        db.flush()
        chunk_appearances[extracted.name] = appearance

    for rel in chunk.relationships:
        if rel.relation_type not in valid_relation_types:
            logger.warning(
                "Relation type %r not in domain — skipping", rel.relation_type
            )
            continue

        from_id = name_to_id.get(rel.from_entity_name)
        to_id = name_to_id.get(rel.to_entity_name)
        if from_id is None or to_id is None:
            logger.warning(
                "Could not resolve relationship endpoints: %r → %r",
                rel.from_entity_name,
                rel.to_entity_name,
            )
            continue
        if from_id == to_id:
            continue

        from_appearance = chunk_appearances.get(rel.from_entity_name)
        if from_appearance is None:
            logger.warning(
                "No appearance found for relationship source %r in chunk %d",
                rel.from_entity_name,
                chunk.passage_index,
            )
            continue

        db.add(
            EntityLink(
                from_entity_id=from_id,
                relation_type=rel.relation_type,
                to_entity_id=to_id,
                appearance_id=from_appearance.id,
                raw_excerpt=rel.raw_excerpt,
                synthesized_description=rel.synthesized_description,
            )
        )

        if rel.relation_type in bidir_types:
            to_appearance = chunk_appearances.get(rel.to_entity_name)
            appearance_id_for_reverse = (
                to_appearance.id if to_appearance is not None else from_appearance.id
            )
            db.add(
                EntityLink(
                    from_entity_id=to_id,
                    relation_type=rel.relation_type,
                    to_entity_id=from_id,
                    appearance_id=appearance_id_for_reverse,
                    raw_excerpt=rel.raw_excerpt,
                    synthesized_description=rel.synthesized_description,
                )
            )


def _fail(doc: Document, error: str, db: Session) -> None:
    doc.ingestion_status = "failed"
    doc.ingestion_error = error
    try:
        db.commit()
    except Exception:
        db.rollback()
