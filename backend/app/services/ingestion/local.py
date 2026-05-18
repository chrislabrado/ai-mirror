"""Local-model parser for Ollama / Open WebUI / LM Studio / AnythingLLM exports."""
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


def _iso(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class LocalModelIngestor(BaseIngestor):
    """Catches generic OpenAI-style or Open WebUI chat exports."""

    source_slug = "local"
    display_name = "Local model"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".json":
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:4096]
        return '"messages"' in text and (
            '"role"' in text or "open-webui" in text.lower() or "ollama" in text.lower()
        )

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        data = json.loads(payload.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "messages" in data:
            yield self._parse_one(data)
            return
        if isinstance(data, list):
            for conv in data:
                yield self._parse_one(conv)
            return
        if isinstance(data, dict) and "chats" in data:
            for conv in data["chats"]:
                yield self._parse_one(conv)

    def _parse_one(self, conv: dict) -> NormalisedConversation:
        messages: list[NormalisedMessage] = []
        for seq, m in enumerate(conv.get("messages") or []):
            role = m.get("role") or "user"
            content = m.get("content") or m.get("text") or ""
            if isinstance(content, list):
                content = "\n\n".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in content
                )
            if not content or not content.strip():
                continue
            messages.append(
                NormalisedMessage(
                    role=role,
                    content=content.strip(),
                    sequence=seq,
                    message_at=_iso(m.get("created_at") or m.get("timestamp")),
                )
            )
        return NormalisedConversation(
            external_id=conv.get("id"),
            title=conv.get("title") or conv.get("name"),
            started_at=_iso(conv.get("created_at") or conv.get("createdAt")),
            ended_at=_iso(conv.get("updated_at") or conv.get("updatedAt")),
            messages=messages,
            raw_metadata={"model": conv.get("model")},
        )
