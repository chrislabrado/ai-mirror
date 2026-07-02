from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.epoch import EpochProfile, Trajectory
from app.schemas.temporal import (
    EpochOut,
    EpochsResponse,
    TemporalRefreshRequest,
    TemporalRefreshResponse,
    TrajectoriesRequest,
    TrajectoriesResponse,
    TrajectoryOut,
)
from app.services.llm import LLMUnavailable
from app.services.temporal import (
    compute_epoch_stats,
    profile_epochs,
    synthesize_trajectories,
)

router = APIRouter(prefix="/temporal", tags=["temporal"])


def _trajectory_out(row: Trajectory) -> TrajectoryOut:
    return TrajectoryOut(
        metric=row.metric,
        series=row.series or [],
        narrative=row.narrative,
        assumptions=row.assumptions,
        model_used=row.model_used,
        created_at=row.created_at,
    )


@router.get("/epochs", response_model=EpochsResponse)
async def list_epochs(db: AsyncSession = Depends(get_db)) -> EpochsResponse:
    """All-sources monthly epoch rows: deterministic stats + cached LLM profile."""
    rows = (
        (
            await db.execute(
                select(EpochProfile)
                .where(
                    EpochProfile.epoch_kind == "month",
                    EpochProfile.source_slug.is_(None),
                )
                .order_by(EpochProfile.epoch_start)
            )
        )
        .scalars()
        .all()
    )
    return EpochsResponse(
        epochs=[
            EpochOut(
                epoch=f"{r.epoch_start.year:04d}-{r.epoch_start.month:02d}",
                stats=r.stats or {},
                profile=r.profile,
                model_used=r.model_used,
            )
            for r in rows
        ]
    )


@router.post("/refresh", response_model=TemporalRefreshResponse)
async def refresh_temporal(
    payload: TemporalRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TemporalRefreshResponse:
    """Recompute deterministic epoch stats, then profile unprofiled epochs (scaffold tier)."""
    started = time.monotonic()
    stats = await compute_epoch_stats(db)
    try:
        profiled = await profile_epochs(db, fable=payload.fable, force=payload.force)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TemporalRefreshResponse(
        epochs_total=len(stats),
        epochs_profiled=profiled,
        duration_seconds=round(time.monotonic() - started, 2),
    )


@router.post("/trajectories", response_model=TrajectoriesResponse)
async def create_trajectories(
    payload: TrajectoriesRequest,
    db: AsyncSession = Depends(get_db),
) -> TrajectoriesResponse:
    """Synthesize observed + extrapolated trajectory series (hard tier, latest-wins)."""
    try:
        rows = await synthesize_trajectories(db, fable=payload.fable)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TrajectoriesResponse(trajectories=[_trajectory_out(r) for r in rows])


@router.get("/trajectories", response_model=TrajectoriesResponse)
async def latest_trajectories(db: AsyncSession = Depends(get_db)) -> TrajectoriesResponse:
    """Latest persisted standalone trajectory set (report_id IS NULL)."""
    rows = (
        (
            await db.execute(
                select(Trajectory)
                .where(Trajectory.report_id.is_(None))
                .order_by(Trajectory.id)
            )
        )
        .scalars()
        .all()
    )
    return TrajectoriesResponse(trajectories=[_trajectory_out(r) for r in rows])
