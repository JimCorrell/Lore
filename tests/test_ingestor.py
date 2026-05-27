import uuid


from app.models.appearance import Appearance
from app.models.document import Document
from app.models.domain import Domain
from app.models.entity import Entity
from app.models.entity_link import EntityLink
from app.services.extraction import ChunkResult, ExtractedEntity, ExtractedRelationship
from app.services.ingestor import ingest_document


def _make_domain(db) -> Domain:
    domain = Domain(
        id="test-domain",
        name="Test Domain",
        entity_types=["CHARACTER", "LOCATION"],
        relation_types=[
            {"type": "COMMANDS", "bidirectional": False},
            {"type": "ALLIED_WITH", "bidirectional": True},
        ],
        attribute_schema={},
    )
    db.add(domain)
    db.flush()
    return domain


def _make_document(domain_id: str, db) -> Document:
    doc = Document(
        domain_id=domain_id,
        title="Test Doc",
        source_type="novel",
        ingestion_status="pending",
    )
    db.add(doc)
    db.flush()
    return doc


class TestIngestDocument:
    def test_sets_status_complete(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        monkeypatch.setattr(
            "app.services.ingestor.extract_document",
            lambda text, d: [
                ChunkResult(
                    passage_index=0,
                    entities=[
                        ExtractedEntity(
                            name="Hero",
                            type="CHARACTER",
                            raw_excerpt="Hero ran.",
                            synthesized_description="A hero.",
                        )
                    ],
                    relationships=[],
                    extraction_model="test",
                )
            ],
        )

        ingest_document(doc.id, "Hero ran.", db)
        db.refresh(doc)
        assert doc.ingestion_status == "complete"
        assert doc.ingestion_error is None

    def test_writes_appearances(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        monkeypatch.setattr(
            "app.services.ingestor.extract_document",
            lambda text, d: [
                ChunkResult(
                    passage_index=0,
                    entities=[
                        ExtractedEntity(
                            name="Hero",
                            type="CHARACTER",
                            raw_excerpt="Hero ran.",
                            synthesized_description="A hero.",
                        )
                    ],
                    relationships=[],
                    extraction_model="test",
                )
            ],
        )

        ingest_document(doc.id, "Hero ran.", db)
        appearances = db.query(Appearance).filter_by(document_id=doc.id).all()
        assert len(appearances) == 1
        assert appearances[0].raw_excerpt == "Hero ran."

    def test_writes_entity(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        monkeypatch.setattr(
            "app.services.ingestor.extract_document",
            lambda text, d: [
                ChunkResult(
                    passage_index=0,
                    entities=[
                        ExtractedEntity(
                            name="New Character",
                            type="CHARACTER",
                            raw_excerpt="...",
                            synthesized_description="...",
                        )
                    ],
                    relationships=[],
                    extraction_model="test",
                )
            ],
        )

        ingest_document(doc.id, "...", db)
        entity = (
            db.query(Entity)
            .filter_by(canonical_name="New Character", domain_id=domain.id)
            .first()
        )
        assert entity is not None

    def test_writes_directed_link(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        monkeypatch.setattr(
            "app.services.ingestor.extract_document",
            lambda text, d: [
                ChunkResult(
                    passage_index=0,
                    entities=[
                        ExtractedEntity(
                            name="Commander",
                            type="CHARACTER",
                            raw_excerpt="...",
                            synthesized_description="...",
                        ),
                        ExtractedEntity(
                            name="Soldier",
                            type="CHARACTER",
                            raw_excerpt="...",
                            synthesized_description="...",
                        ),
                    ],
                    relationships=[
                        ExtractedRelationship(
                            from_entity_name="Commander",
                            relation_type="COMMANDS",
                            to_entity_name="Soldier",
                            raw_excerpt="...",
                            synthesized_description="...",
                        )
                    ],
                    extraction_model="test",
                )
            ],
        )

        ingest_document(doc.id, "...", db)
        links = db.query(EntityLink).all()
        assert len(links) == 1
        commander = db.query(Entity).filter_by(canonical_name="Commander").first()
        assert links[0].from_entity_id == commander.id
        assert links[0].relation_type == "COMMANDS"

    def test_bidirectional_relation_writes_two_links(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        monkeypatch.setattr(
            "app.services.ingestor.extract_document",
            lambda text, d: [
                ChunkResult(
                    passage_index=0,
                    entities=[
                        ExtractedEntity(
                            name="Alpha",
                            type="CHARACTER",
                            raw_excerpt="...",
                            synthesized_description="...",
                        ),
                        ExtractedEntity(
                            name="Beta",
                            type="CHARACTER",
                            raw_excerpt="...",
                            synthesized_description="...",
                        ),
                    ],
                    relationships=[
                        ExtractedRelationship(
                            from_entity_name="Alpha",
                            relation_type="ALLIED_WITH",
                            to_entity_name="Beta",
                            raw_excerpt="...",
                            synthesized_description="...",
                        )
                    ],
                    extraction_model="test",
                )
            ],
        )

        ingest_document(doc.id, "...", db)
        links = db.query(EntityLink).filter_by(relation_type="ALLIED_WITH").all()
        assert len(links) == 2
        endpoints = {(str(lnk.from_entity_id), str(lnk.to_entity_id)) for lnk in links}
        alpha = db.query(Entity).filter_by(canonical_name="Alpha").first()
        beta = db.query(Entity).filter_by(canonical_name="Beta").first()
        assert (str(alpha.id), str(beta.id)) in endpoints
        assert (str(beta.id), str(alpha.id)) in endpoints

    def test_claude_error_sets_status_failed(self, db, monkeypatch):
        domain = _make_domain(db)
        doc = _make_document(domain.id, db)

        def _raise(text, d):
            raise RuntimeError("Claude is down")

        monkeypatch.setattr("app.services.ingestor.extract_document", _raise)

        ingest_document(doc.id, "...", db)
        db.refresh(doc)
        assert doc.ingestion_status == "failed"
        assert "Claude is down" in doc.ingestion_error

    def test_unknown_document_id_is_no_op(self, db):
        ingest_document(uuid.uuid4(), "text", db)  # should not raise
