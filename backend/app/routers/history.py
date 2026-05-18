from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.conversation import Conversation, Source
from app.models.message import Message
from app.schemas.history import (
    ConversationDetail,
    ConversationListItem,
    ConversationListResponse,
    MessageOut,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    q: str | None = Query(default=None, description="Title substring filter (case-insensitive)"),
    source: str | None = Query(default=None, description="Source slug filter"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """Paginated list of conversations, ordered by updated_at DESC."""
    base_q = (
        select(Conversation, Source)
        .join(Source, Conversation.source_id == Source.id)
    )
    if q:
        base_q = base_q.where(Conversation.title.ilike(f"%{q}%"))
    if source:
        base_q = base_q.where(Source.slug == source)

    # Total count
    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = (await db.execute(count_q)).scalar_one()

    # Paginated rows
    rows_q = base_q.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(rows_q)
    rows = result.all()

    items = [
        ConversationListItem(
            id=conv.id,
            source_slug=src.slug,
            source_name=src.display_name,
            title=conv.title,
            message_count=conv.message_count,
            started_at=conv.started_at,
            updated_at=conv.updated_at,
        )
        for conv, src in rows
    ]
    return ConversationListResponse(items=items, total=total)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """Single conversation with all messages ordered by sequence."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            selectinload(Conversation.source),
            selectinload(Conversation.messages),
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = sorted(conv.messages, key=lambda m: m.sequence)
    return ConversationDetail(
        id=conv.id,
        source_slug=conv.source.slug,
        source_name=conv.source.display_name,
        title=conv.title,
        summary=conv.summary,
        message_count=conv.message_count,
        started_at=conv.started_at,
        ended_at=conv.ended_at,
        messages=[
            MessageOut(
                id=m.id,
                sequence=m.sequence,
                role=m.role,
                content=m.content,
                message_at=m.message_at,
            )
            for m in messages
        ],
    )
