import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql://lore:lore_dev@localhost:5433/lore_test"

_engine = create_engine(TEST_DATABASE_URL)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db():
    connection = _engine.connect()
    transaction = connection.begin()
    session = _TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Domain fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def star_wars_domain(db):
    from app.models.domain import Domain

    domain = Domain(
        id="star-wars",
        name="Star Wars Canon",
        entity_types=["CHARACTER", "LOCATION", "FACTION", "SHIP"],
        relation_types=[
            {"type": "COMMANDS", "bidirectional": False},
            {"type": "ALLIED_WITH", "bidirectional": True},
            {"type": "MEMBER_OF", "bidirectional": False},
        ],
        extraction_hints="Extract Star Wars entities.",
        attribute_schema={
            "CHARACTER": ["species", "affiliation"],
            "LOCATION": ["region", "type"],
        },
    )
    db.add(domain)
    db.flush()
    return domain
