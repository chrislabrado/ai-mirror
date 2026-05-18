from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.insights import DeepDiveRequest, DeepDiveResponse, InsightsAggregated
from app.services.insights import get_aggregated_insights
from app.services.reports import run_deep_dive

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/aggregated", response_model=InsightsAggregated)
async def aggregated_insights(
    db: AsyncSession = Depends(get_db),
) -> InsightsAggregated:
    """Aggregate ReportBlock rows across all reports grouped by block_type."""
    return await get_aggregated_insights(db=db)


@router.post("/deep-dive", response_model=DeepDiveResponse)
async def deep_dive(
    request: DeepDiveRequest,
    db: AsyncSession = Depends(get_db),
) -> DeepDiveResponse:
    """Run a focused deep-dive analysis on a specific insight theme.

    Requires at least one Full Mirror report to have been run first.
    Returns a rich multi-paragraph analysis plus evidence citations,
    and persists the result as a new 'deep_dive' report.
    """
    return await run_deep_dive(db, request)
