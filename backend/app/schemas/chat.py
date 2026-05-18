from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Evidence


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatHistoryRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage] = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=20)


class ChatHistoryResponse(BaseModel):
    session_id: str
    reply: str
    evidence: list[Evidence] = []
    model_used: str | None = None
