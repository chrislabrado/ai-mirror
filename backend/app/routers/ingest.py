from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ingest import IngestResponse, RemoteIngestRequest, SourceSlug
from app.services.ingestion.pipeline import run_ingestion
from app.services.ingestion.remote import run_remote_ingestion

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_archive(
    file: UploadFile = File(..., description="Exported archive (zip / json / md)."),
    source: SourceSlug = Form("auto"),
    label: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Accept an exported conversation archive and run the ingestion pipeline.

    Supported sources: chatgpt, claude, grok, gemini, perplexity, local, auto.
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename.")
    try:
        result = await run_ingestion(db=db, upload=file, source=source, label=label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/remote", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_remote(
    request: RemoteIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest conversation files directly from an allowed local root.

    Connectors: claude_code (~/.claude/projects), openclaw (~/.openclaw/agents),
    path (explicit directory — must be inside an allowed ingest root).
    """
    try:
        result = await run_remote_ingestion(
            db=db,
            connector=request.connector,
            path=request.path,
            since=request.since,
            limit=request.limit,
            label=request.label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
