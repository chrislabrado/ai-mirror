from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel


class MessageOut(ORMModel):
    id: int
    sequence: int
    role: str
    content: str
    message_at: datetime | None = None


class ConversationListItem(ORMModel):
    id: int
    source_slug: str
    source_name: str
    title: str | None = None
    message_count: int
    started_at: datetime | None = None
    updated_at: datetime


class ConversationDetail(ORMModel):
    id: int
    source_slug: str
    source_name: str
    title: str | None = None
    summary: str | None = None
    message_count: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    messages: list[MessageOut]


class ConversationListResponse(ORMModel):
    items: list[ConversationListItem]
    total: int
