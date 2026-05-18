"""Persistent GraphRAG chat over the user's ingested history."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.chat import ChatHistoryRequest, ChatHistoryResponse
from app.schemas.common import Evidence
from app.services.embeddings import get_collection
from app.services.llm import chat_json, llm_available
from app.utils.logger import get_logger

log = get_logger(__name__)


async def answer_history_chat(
    *, db: AsyncSession, request: ChatHistoryRequest  # noqa: ARG001 — db reserved for future joins
) -> ChatHistoryResponse:
    session_id = request.session_id or str(uuid.uuid4())
    user_msg = request.messages[-1].content

    evidence: list[Evidence] = []
    snippets: list[str] = []
    try:
        result = get_collection().query(query_texts=[user_msg], n_results=request.top_k)
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        for doc, meta in zip(docs, metas, strict=False):
            snippets.append(doc[:600])
            evidence.append(
                Evidence(
                    message_id=meta.get("message_id") if isinstance(meta, dict) else None,
                    conversation_id=meta.get("conversation_id") if isinstance(meta, dict) else None,
                    snippet=doc[:300],
                    source_slug=meta.get("source_slug") if isinstance(meta, dict) else None,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.info("chat.embed_query_unavailable", extra={"error": str(exc)})

    if not llm_available():
        reply = (
            "I haven't been configured with an LLM yet, sir. Set `LLM_PROVIDER` "
            "and an API key (or enable the `local-llm` profile) to talk to your "
            "history."
        )
        return ChatHistoryResponse(session_id=session_id, reply=reply, evidence=evidence)

    history_text = "\n\n".join(f"[{m.role}] {m.content}" for m in request.messages[-12:])
    corpus = "\n\n---\n\n".join(snippets) if snippets else "(no retrieved excerpts)"

    payload: dict[str, Any] = await chat_json(
        system=(
            "You are AI Mirror's history chat. Answer the user's question using "
            "ONLY the retrieved excerpts from their own ingested AI history. "
            "When uncertain, say so. Be concise. Output JSON only as: "
            "{reply: string}."
        ),
        user=f"CONVERSATION SO FAR:\n{history_text}\n\nRETRIEVED EXCERPTS:\n{corpus}",
        temperature=0.3,
        max_tokens=1200,
    )

    return ChatHistoryResponse(
        session_id=session_id,
        reply=payload.get("reply", ""),
        evidence=evidence,
        model_used=f"{settings.llm_provider}:{settings.llm_model}",
    )
