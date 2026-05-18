"""ChatGPT (OpenAI) export parser.

Format: ``conversations.json`` inside the OpenAI Data Export ZIP. Each item
has a ``mapping`` of node id -> {message: {author, content, create_time}}.
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


class ChatGPTIngestor(BaseIngestor):
    source_slug = "chatgpt"
    display_name = "ChatGPT"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".json":
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:2048]
        return '"mapping"' in text and '"create_time"' in text

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        data = json.loads(payload.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for conv in data:
            yield self._parse_one(conv)

    def _parse_one(self, conv: dict) -> NormalisedConversation:
        mapping = conv.get("mapping", {})
        nodes = list(mapping.values())

        messages: list[NormalisedMessage] = []
        seq = 0
        for node in nodes:
            msg = node.get("message")
            if not msg:
                continue
            author = (msg.get("author") or {}).get("role", "unknown")
            parts = (msg.get("content") or {}).get("parts") or []
            text = "\n\n".join(p for p in parts if isinstance(p, str)).strip()
            if not text:
                continue
            ct = msg.get("create_time")
            messages.append(
                NormalisedMessage(
                    role=author,
                    content=text,
                    sequence=seq,
                    message_at=datetime.fromtimestamp(ct) if ct else None,
                )
            )
            seq += 1

        ct = conv.get("create_time")
        ut = conv.get("update_time")
        return NormalisedConversation(
            external_id=conv.get("id") or conv.get("conversation_id"),
            title=conv.get("title"),
            started_at=datetime.fromtimestamp(ct) if ct else None,
            ended_at=datetime.fromtimestamp(ut) if ut else None,
            messages=messages,
            raw_metadata={"model": conv.get("default_model_slug")},
        )
