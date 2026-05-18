from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import GaugeSet


class DashboardSummary(BaseModel):
    last_run_at: datetime | None = None
    last_run_kind: str | None = None
    bullets: list[str]
    gauges: GaugeSet | None = None
    total_conversations: int
    total_messages: int
    sources: list[dict[str, str | int]]
