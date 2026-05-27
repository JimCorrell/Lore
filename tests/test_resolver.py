from app.models.entity import Entity
from app.models.merge_event import MergeEvent
from app.services.extraction import ExtractedEntity
from app.services.resolver import resolve_entities


def _make_entity(name: str, domain_id: str, aliases: list[str], db) -> Entity:
    e = Entity(
        canonical_name=name,
        entity_type="CHARACTER",
        aliases=aliases,
        domain_id=domain_id,
        appearance_count=1,
    )
    db.add(e)
    db.flush()
    return e


def _extracted(name: str) -> ExtractedEntity:
    return ExtractedEntity(
        name=name,
        type="CHARACTER",
        aliases=[],
        raw_excerpt="...",
        synthesized_description="...",
    )


VALID_TYPES = ["CHARACTER", "LOCATION", "FACTION", "SHIP"]


class TestExactCanonicalNameMatch:
    def test_returns_existing_entity_id(self, db, star_wars_domain):
        existing = _make_entity("Luke Skywalker", "star-wars", [], db)
        result = resolve_entities(
            [_extracted("Luke Skywalker")], "star-wars", VALID_TYPES, db
        )
        assert result["Luke Skywalker"] == existing.id

    def test_case_insensitive(self, db, star_wars_domain):
        existing = _make_entity("Darth Vader", "star-wars", [], db)
        result = resolve_entities(
            [_extracted("darth vader")], "star-wars", VALID_TYPES, db
        )
        assert result["darth vader"] == existing.id

    def test_increments_appearance_count(self, db, star_wars_domain):
        existing = _make_entity("Obi-Wan Kenobi", "star-wars", [], db)
        assert existing.appearance_count == 1
        resolve_entities([_extracted("Obi-Wan Kenobi")], "star-wars", VALID_TYPES, db)
        db.refresh(existing)
        assert existing.appearance_count == 2


class TestExactAliasMatch:
    def test_matches_on_alias(self, db, star_wars_domain):
        existing = _make_entity(
            "Anakin Skywalker", "star-wars", ["Darth Vader", "Ani"], db
        )
        result = resolve_entities(
            [_extracted("Darth Vader")], "star-wars", VALID_TYPES, db
        )
        assert result["Darth Vader"] == existing.id

    def test_alias_match_increments_count(self, db, star_wars_domain):
        existing = _make_entity(
            "Han Solo", "star-wars", ["Scruffy-looking nerf herder"], db
        )
        resolve_entities(
            [_extracted("Scruffy-looking nerf herder")], "star-wars", VALID_TYPES, db
        )
        db.refresh(existing)
        assert existing.appearance_count == 2


class TestFuzzyMatch:
    def test_fuzzy_match_reuses_entity(self, db, star_wars_domain):
        existing = _make_entity("Chewbacca", "star-wars", [], db)
        result = resolve_entities(
            [_extracted("Chewbaca")], "star-wars", VALID_TYPES, db
        )
        assert result.get("Chewbaca") == existing.id

    def test_fuzzy_match_writes_merge_event(self, db, star_wars_domain):
        _make_entity("Chewbacca", "star-wars", [], db)
        resolve_entities([_extracted("Chewbaca")], "star-wars", VALID_TYPES, db)
        event = db.query(MergeEvent).filter_by(absorbed_name="Chewbaca").first()
        assert event is not None
        assert event.match_method == "fuzzy"
        assert event.match_score is not None

    def test_fuzzy_match_sets_auto_merged_status(self, db, star_wars_domain):
        existing = _make_entity("Chewbacca", "star-wars", [], db)
        resolve_entities([_extracted("Chewbaca")], "star-wars", VALID_TYPES, db)
        db.refresh(existing)
        assert existing.merge_status == "auto_merged"

    def test_fuzzy_match_appends_absorbed_name_to_aliases(self, db, star_wars_domain):
        existing = _make_entity("Chewbacca", "star-wars", [], db)
        resolve_entities([_extracted("Chewbaca")], "star-wars", VALID_TYPES, db)
        db.refresh(existing)
        assert "Chewbaca" in existing.aliases


class TestNoMatch:
    def test_creates_new_entity(self, db, star_wars_domain):
        result = resolve_entities(
            [_extracted("Jar Jar Binks")], "star-wars", VALID_TYPES, db
        )
        entity_id = result.get("Jar Jar Binks")
        assert entity_id is not None
        entity = db.get(Entity, entity_id)
        assert entity.canonical_name == "Jar Jar Binks"
        assert entity.appearance_count == 1

    def test_does_not_create_entity_for_invalid_type(self, db, star_wars_domain):
        extracted = ExtractedEntity(
            name="Some Thing",
            type="UNKNOWN_TYPE",
            raw_excerpt="...",
            synthesized_description="...",
        )
        result = resolve_entities([extracted], "star-wars", VALID_TYPES, db)
        assert "Some Thing" not in result

    def test_deduplicates_within_batch(self, db, star_wars_domain):
        batch = [_extracted("New Entity"), _extracted("New Entity")]
        result = resolve_entities(batch, "star-wars", VALID_TYPES, db)
        assert "New Entity" in result
        count = (
            db.query(Entity)
            .filter_by(canonical_name="New Entity", domain_id="star-wars")
            .count()
        )
        assert count == 1
