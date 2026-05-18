"""Claude (Anthropic) export parser.

Format: ``conversations.json`` containing a list of conversations each with
``chat_messages: [{sender: 'human'|'assistant', text, created_at}]``.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from app.services.ingestion.base import (
    BaseIngestor,
    NormalisedConversation,
    NormalisedMessage,
)


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ClaudeIngestor(BaseIngestor):
    source_slug = "claude"
    display_name = "Claude"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".json":
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:4096]
        return '"chat_messages"' in text or '"sender":"human"' in text

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        data = json.loads(payload.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for conv in data:
            yield self._parse_one(conv)

    def _parse_one(self, conv: dict) -> NormalisedConversation:
        messages: list[NormalisedMessage] = []
        for seq, msg in enumerate(conv.get("chat_messages", []) or []):
            sender = msg.get("sender", "unknown")
            role = "user" if sender == "human" else "assistant" if sender == "assistant" else sender
            text = msg.get("text") or ""
            if not text and msg.get("content"):
                parts = msg["content"]
                if isinstance(parts, list):
                    text = "\n\n".join(p.get("text", "") for p in parts if isinstance(p, dict))
            if not text.strip():
                continue
            messages.append(
                NormalisedMessage(
                    role=role,
                    content=text.strip(),
                    sequence=seq,
                    message_at=_iso(msg.get("created_at")),
                )
            )

        return NormalisedConversation(
            external_id=conv.get("uuid") or conv.get("id"),
            title=conv.get("name") or conv.get("title"),
            started_at=_iso(conv.get("created_at")),
            ended_at=_iso(conv.get("updated_at")),
            messages=messages,
            raw_metadata={"account": conv.get("account_uuid")},
        )
