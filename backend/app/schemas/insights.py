from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Evidence


class AggregatedBlock(BaseModel):
    block_type: str
    heading: str | None = None
    occurrence_count: int
    sample_body: str
    latest_report_id: int
    latest_created_at: datetime


class InsightsAggregated(BaseModel):
    total_reports: int
    total_blocks: int
    blocks: list[AggregatedBlock]


class DeepDiveRequest(BaseModel):
    block_type: str
    focus_question: str | None = None
    sources: list[str] | None = None


class DeepDiveResponse(BaseModel):
    block_type: str
    heading: str
    body_markdown: str
    evidence: list[Evidence]
    source_report_id: int | None
    model_used: str | None
    duration_seconds: float
    created_at: datetime
