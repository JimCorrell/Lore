import uuid

import pytest

from app.models.appearance import Appearance
from app.models.document import Document
from app.services.extraction import ChunkResult


def _canned_chunk_result() -> ChunkResult:
    from app.services.extraction import ExtractedEntity

    return ChunkResult(
        passage_index=0,
        entities=[
            ExtractedEntity(
                name="Luke Skywalker",
                type="CHARACTER",
                raw_excerpt="Luke ran across the desert.",
                synthesized_description="Luke is a young man from Tatooine.",
            )
        ],
        relationships=[],
        extraction_model="claude-sonnet-4-6",
    )


@pytest.fixture
def mock_extract(monkeypatch):
    """Patch extract_document so tests don't hit the real Claude API."""
    monkeypatch.setattr(
        "app.services.ingestor.extract_document",
        lambda text, domain: [_canned_chunk_result()],
    )


class TestCreateDocument:
    def test_returns_pending_status(self, client, star_wars_domain, mock_extract):
        resp = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "A New Hope",
                "source_type": "novel",
                "text": "Luke ran across the desert.",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["ingestion_status"] == "pending"
        assert resp.json()["title"] == "A New Hope"

    def test_invalid_domain_returns_404(self, client, mock_extract):
        resp = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "nonexistent",
                "title": "Test",
                "source_type": "novel",
                "text": "Some text.",
            },
        )
        assert resp.status_code == 404

    def test_re_ingest_complete_document_resets_and_requeues(
        self, client, db, star_wars_domain, mock_extract
    ):
        resp1 = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Original",
                "source_type": "novel",
                "external_id": "dup-001",
                "text": "Luke ran.",
            },
        )
        assert resp1.status_code == 201
        doc_id = resp1.json()["id"]

        # Simulate complete status
        doc = db.get(Document, doc_id)
        doc.ingestion_status = "complete"
        db.commit()

        resp2 = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Updated",
                "source_type": "novel",
                "external_id": "dup-001",
                "text": "Luke ran again.",
            },
        )
        assert resp2.status_code == 201
        assert resp2.json()["id"] == doc_id
        assert resp2.json()["title"] == "Updated"
        assert resp2.json()["ingestion_status"] == "pending"

    def test_re_ingest_while_processing_returns_409(
        self, client, db, star_wars_domain, mock_extract
    ):
        resp1 = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Processing Doc",
                "source_type": "novel",
                "external_id": "proc-001",
                "text": "Luke ran.",
            },
        )
        doc_id = resp1.json()["id"]
        doc = db.get(Document, doc_id)
        doc.ingestion_status = "processing"
        db.commit()

        resp2 = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Processing Doc",
                "source_type": "novel",
                "external_id": "proc-001",
                "text": "Luke ran.",
            },
        )
        assert resp2.status_code == 409


class TestListDocuments:
    def test_list_all(self, client, db, star_wars_domain, mock_extract):
        client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Doc A",
                "source_type": "novel",
                "text": "x",
            },
        )
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_by_domain(self, client, db, star_wars_domain, mock_extract):
        client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "SW Doc",
                "source_type": "novel",
                "text": "x",
            },
        )
        resp = client.get("/api/v1/documents?domain_id=star-wars")
        assert resp.status_code == 200
        assert all(d["domain_id"] == "star-wars" for d in resp.json())

    def test_filter_by_status(self, client, db, star_wars_domain, mock_extract):
        resp = client.get("/api/v1/documents?ingestion_status=pending")
        assert resp.status_code == 200
        assert all(d["ingestion_status"] == "pending" for d in resp.json())


class TestGetDocument:
    def test_returns_document(self, client, star_wars_domain, mock_extract):
        create_resp = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Get Me",
                "source_type": "novel",
                "text": "x",
            },
        )
        doc_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    def test_not_found(self, client):
        resp = client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestDeleteDocument:
    def test_delete_removes_document(self, client, star_wars_domain, mock_extract):
        create_resp = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Delete Me",
                "source_type": "novel",
                "text": "x",
            },
        )
        doc_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 204
        get_resp = client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 404

    def test_delete_cascades_appearances(
        self, client, db, star_wars_domain, mock_extract
    ):
        create_resp = client.post(
            "/api/v1/documents",
            json={
                "domain_id": "star-wars",
                "title": "Cascade Test",
                "source_type": "novel",
                "text": "x",
            },
        )
        doc_id = create_resp.json()["id"]
        # Manually add an appearance to verify cascade
        from app.models.entity import Entity

        entity = Entity(
            canonical_name="Test Entity",
            entity_type="CHARACTER",
            aliases=[],
            domain_id="star-wars",
            appearance_count=1,
        )
        db.add(entity)
        db.flush()
        appearance = Appearance(
            entity_id=entity.id,
            document_id=doc_id,
            raw_excerpt="test",
            synthesized_description="test",
        )
        db.add(appearance)
        db.commit()

        client.delete(f"/api/v1/documents/{doc_id}")
        remaining = db.query(Appearance).filter_by(document_id=doc_id).count()
        assert remaining == 0
