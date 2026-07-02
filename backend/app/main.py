from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.config import settings
from app.database import init_db
from app.routers import (
    chat,
    dashboard,
    export_guide,
    focus_lens,
    graph,
    history,
    ingest,
    insights,
    reports,
    temporal,
)
from app.utils.logger import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    log.info("ai_mirror.startup", extra={"env": settings.app_env, "version": settings.app_version})
    await init_db()
    yield
    log.info("ai_mirror.shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Privacy-first, local-first personal second-brain and self-reflection engine. "
        "Ingests AI conversation history, builds a knowledge graph and embeddings, "
        "and generates natural-language analysis of the user's own thinking."
    ),
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


# --- API routers ---
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(export_guide.router)
app.include_router(focus_lens.router)
app.include_router(graph.router)
app.include_router(history.router)
app.include_router(ingest.router)
app.include_router(insights.router)
app.include_router(reports.router)
app.include_router(temporal.router)
