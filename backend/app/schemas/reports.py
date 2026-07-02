from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import GaugeSet, ORMModel, ReportBlockOut


class ReportRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    sources: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2048)
    fable: bool | None = Field(
        default=None,
        description=(
            "Tiered-model override: true forces fable mode (scaffold model for "
            "mechanical passes, hard model for synthesis/critique), false forces "
            "single-model, null uses the FABLE_MODE server setting."
        ),
    )


class MetaAnalysisRequest(BaseModel):
    compare_last: int = Field(default=5, ge=2, le=20)
    fable: bool | None = None


class ReportResponse(BaseModel):
    report_id: int
    kind: str
    title: str
    summary: str
    gauges: GaugeSet | None = None
    blocks: list[ReportBlockOut]
    model_used: str | None = None
    created_at: datetime


class ReportListItem(ORMModel):
    id: int
    kind: str
    title: str
    summary: str | None = None
    model_used: str | None = None
    created_at: datetime


class ReportListResponse(ORMModel):
    items: list[ReportListItem]
    total: int
