import uuid


from app.models.appearance import Appearance
from app.models.document import Document
from app.models.entity import Entity


def _make_entity(name: str, entity_type: str, domain_id: str, db) -> Entity:
    e = Entity(
        canonical_name=name,
        entity_type=entity_type,
        aliases=[],
        domain_id=domain_id,
        appearance_count=0,
    )
    db.add(e)
    db.flush()
    return e


def _make_document(
    domain_id: str, title: str, timeline_position: float | None, db
) -> Document:
    doc = Document(
        domain_id=domain_id,
        title=title,
        source_type="novel",
        timeline_position=timeline_position,
        ingestion_status="complete",
    )
    db.add(doc)
    db.flush()
    return doc


class TestListEntities:
    def test_list_all(self, client, db, star_wars_domain):
        _make_entity("Leia Organa", "CHARACTER", "star-wars", db)
        resp = client.get("/api/v1/entities")
        assert resp.status_code == 200
        assert any(e["canonical_name"] == "Leia Organa" for e in resp.json())

    def test_filter_by_domain(self, client, db, star_wars_domain):
        _make_entity("R2-D2", "CHARACTER", "star-wars", db)
        resp = client.get("/api/v1/entities?domain_id=star-wars")
        assert resp.status_code == 200
        assert all(e["domain_id"] == "star-wars" for e in resp.json())

    def test_filter_by_entity_type(self, client, db, star_wars_domain):
        _make_entity("Tatooine", "LOCATION", "star-wars", db)
        resp = client.get("/api/v1/entities?domain_id=star-wars&entity_type=LOCATION")
        assert resp.status_code == 200
        assert all(e["entity_type"] == "LOCATION" for e in resp.json())

    def test_filter_by_merge_status(self, client, db, star_wars_domain):
        e = _make_entity("Vader", "CHARACTER", "star-wars", db)
        e.merge_status = "auto_merged"
        db.flush()
        resp = client.get("/api/v1/entities?merge_status=auto_merged")
        assert resp.status_code == 200
        assert all(e["merge_status"] == "auto_merged" for e in resp.json())

    def test_pagination(self, client, db, star_wars_domain):
        for i in range(5):
            _make_entity(f"Entity {i}", "CHARACTER", "star-wars", db)
        resp = client.get("/api/v1/entities?limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2


class TestGetEntity:
    def test_returns_entity(self, client, db, star_wars_domain):
        e = _make_entity("C-3PO", "CHARACTER", "star-wars", db)
        resp = client.get(f"/api/v1/entities/{e.id}")
        assert resp.status_code == 200
        assert resp.json()["canonical_name"] == "C-3PO"

    def test_not_found(self, client):
        resp = client.get(f"/api/v1/entities/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestBiography:
    def test_biography_returns_entity_and_appearances(
        self, client, db, star_wars_domain
    ):
        entity = _make_entity("Han Solo", "CHARACTER", "star-wars", db)
        doc = _make_document("star-wars", "A New Hope", 0.0, db)
        appearance = Appearance(
            entity_id=entity.id,
            document_id=doc.id,
            raw_excerpt="Han shot first.",
            synthesized_description="Han is a smuggler.",
            passage_index=0,
        )
        db.add(appearance)
        db.flush()

        resp = client.get(f"/api/v1/entities/{entity.id}/biography")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"]["canonical_name"] == "Han Solo"
        assert len(data["appearances"]) == 1
        assert data["appearances"][0]["raw_excerpt"] == "Han shot first."

    def test_biography_ordered_by_timeline(self, client, db, star_wars_domain):
        entity = _make_entity("Yoda", "CHARACTER", "star-wars", db)
        doc_anh = _make_document("star-wars", "A New Hope", 0.0, db)
        doc_rots = _make_document("star-wars", "Revenge of the Sith", -19.0, db)

        app_anh = Appearance(
            entity_id=entity.id,
            document_id=doc_anh.id,
            raw_excerpt="ANH Yoda",
            synthesized_description="ANH",
            passage_index=0,
        )
        app_rots = Appearance(
            entity_id=entity.id,
            document_id=doc_rots.id,
            raw_excerpt="ROTS Yoda",
            synthesized_description="ROTS",
            passage_index=0,
        )
        db.add_all([app_anh, app_rots])
        db.flush()

        resp = client.get(f"/api/v1/entities/{entity.id}/biography")
        assert resp.status_code == 200
        excerpts = [a["raw_excerpt"] for a in resp.json()["appearances"]]
        # ROTS (−19) should come before ANH (0)
        assert excerpts.index("ROTS Yoda") < excerpts.index("ANH Yoda")

    def test_biography_nulls_last(self, client, db, star_wars_domain):
        entity = _make_entity("Boba Fett", "CHARACTER", "star-wars", db)
        doc_known = _make_document("star-wars", "Known Timeline", 5.0, db)
        doc_unknown = _make_document("star-wars", "Unknown Timeline", None, db)

        app_known = Appearance(
            entity_id=entity.id,
            document_id=doc_known.id,
            raw_excerpt="Known",
            synthesized_description="...",
            passage_index=0,
        )
        app_unknown = Appearance(
            entity_id=entity.id,
            document_id=doc_unknown.id,
            raw_excerpt="Unknown",
            synthesized_description="...",
            passage_index=0,
        )
        db.add_all([app_known, app_unknown])
        db.flush()

        resp = client.get(f"/api/v1/entities/{entity.id}/biography")
        excerpts = [a["raw_excerpt"] for a in resp.json()["appearances"]]
        assert excerpts.index("Known") < excerpts.index("Unknown")
