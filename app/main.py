from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.routers import health, domains, documents, entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — nothing needed yet; database connections are managed per-request
    yield
    # shutdown — nothing needed yet


app = FastAPI(
    title="Lore",
    version=settings.app_version,
    description=(
        "Corpus-backed knowledge graph service. Ingests unstructured source "
        "documents and extracts named entities, contextual descriptions, and "
        "relationships. Entities accumulate context across the full document "
        "corpus and are retrievable as canonical records, assembled biographies, "
        "or traversable knowledge graph nodes."
    ),
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(domains.router)
app.include_router(documents.router)
app.include_router(entities.router)
