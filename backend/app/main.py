"""
F1 Context Graph AI — FastAPI Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    log.info(f"Starting {settings.app_name}...")

    # Verify Neo4j connectivity (non-fatal — warn if not available)
    try:
        from app.graph.connection import verify_connectivity
        verify_connectivity()
        log.info("✓ Neo4j connected")
    except Exception as e:
        log.warning(f"Neo4j not available: {e}. Graph queries will fail.")

    # Verify PostgreSQL connectivity (non-fatal)
    try:
        from app.db.connection import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        log.info("✓ PostgreSQL connected")
    except Exception as e:
        log.warning(f"PostgreSQL not available: {e}. DB queries will fail.")

    # Verify Qdrant connectivity (non-fatal)
    try:
        from app.vector.connection import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        log.info("✓ Qdrant connected")
    except Exception as e:
        log.warning(f"Qdrant not available: {e}. Document search will fail.")

    log.info(f"✓ {settings.app_name} ready")
    yield

    log.info("Shutting down...")
    try:
        from app.graph.connection import close_neo4j_driver
        close_neo4j_driver()
    except Exception:
        pass


app = FastAPI(
    title="F1 Context Graph AI",
    description="Monaco 2024 F1 conversational AI: FastF1 + PostgreSQL + Neo4j + Qdrant + OpenAI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
