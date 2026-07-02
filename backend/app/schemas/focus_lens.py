from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ReportBlockOut


class FocusLensRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2048)
    date_from: datetime | None = None
    date_to: datetime | None = None
    sources: list[str] | None = None
    max_evidence: int = Field(default=12, ge=1, le=50)
    fable: bool | None = None


class FocusLensResponse(BaseModel):
    report_id: int
    title: str
    summary: str
    blocks: list[ReportBlockOut]
    created_at: datetime
