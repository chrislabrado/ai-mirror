from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import ChatHistoryRequest, ChatHistoryResponse
from app.services.chat_history import answer_history_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/history", response_model=ChatHistoryResponse)
async def chat_history(
    payload: ChatHistoryRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """Persistent GraphRAG chat over the user's ingested AI history."""
    return await answer_history_chat(db=db, request=payload)
