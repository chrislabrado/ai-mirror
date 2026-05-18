from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ingest import IngestResponse, SourceSlug
from app.services.ingestion.pipeline import run_ingestion

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
