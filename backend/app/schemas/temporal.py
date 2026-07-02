from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EpochOut(BaseModel):
    epoch: str  # "YYYY-MM"
    stats: dict
    profile: dict | None = None
    model_used: str | None = None


class EpochsResponse(BaseModel):
    epochs: list[EpochOut]


class TemporalRefreshRequest(BaseModel):
    fable: bool | None = None
    force: bool = False


class TemporalRefreshResponse(BaseModel):
    epochs_total: int
    epochs_profiled: int
    duration_seconds: float


class TrajectoryPoint(BaseModel):
    epoch: str  # "YYYY-MM"
    value: float
    kind: Literal["observed", "extrapolated"]
    ci_low: float | None = None
    ci_high: float | None = None


class TrajectoriesRequest(BaseModel):
    fable: bool | None = None


class TrajectoryOut(BaseModel):
    metric: str
    series: list[TrajectoryPoint]
    narrative: str | None = None
    assumptions: list[str] | None = None
    model_used: str | None = None
    created_at: datetime


class TrajectoriesResponse(BaseModel):
    trajectories: list[TrajectoryOut]
