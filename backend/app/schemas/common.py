from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GaugeSet(BaseModel):
    """Three semi-circular speedometer gauges shown on the Dashboard."""

    thought_clarity: float = Field(ge=0.0, le=1.0)
    self_reflection_depth: float = Field(ge=0.0, le=1.0)
    aptitude_balance: float = Field(ge=0.0, le=1.0)


class Evidence(BaseModel):
    message_id: int | None = None
    conversation_id: int | None = None
    snippet: str
    source_slug: str | None = None
    message_at: datetime | None = None


class ReportBlockOut(ORMModel):
    id: int
    block_type: str
    heading: str | None
    position: int
    body_markdown: str
    structured: dict[str, Any] | None = None
    evidence: list[Evidence] | None = None
