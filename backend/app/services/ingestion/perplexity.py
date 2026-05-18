"""Perplexity export parser.

Supports both the per-thread Markdown export and the bulk JSON dump from
Settings -> Data Controls.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from app.services.ingestion.base import (
    BaseIngestor,
    NormalisedConversation,
    NormalisedMessage,
)

_MD_TURN = re.compile(r"^##\s+(User|Assistant)\s*$", re.MULTILINE)


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class PerplexityIngestor(BaseIngestor):
    source_slug = "perplexity"
    display_name = "Perplexity"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        suffix = payload.suffix.lower()
        if suffix not in {".json", ".md", ".markdown"}:
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:4096]
        return "perplexity" in text.lower() or bool(_MD_TURN.search(text))

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        if payload.suffix.lower() == ".json":
            data = json.loads(payload.read_text(encoding="utf-8"))
            convs = data.get("threads") if isinstance(data, dict) else data
            for conv in convs or []:
                yield self._parse_json(conv)
        else:
            yield self._parse_markdown(payload)

    def _parse_json(self, conv: dict) -> NormalisedConversation:
        messages: list[NormalisedMessage] = []
        for seq, m in enumerate(conv.get("messages", []) or []):
            role = m.get("role") or "user"
            content = m.get("content") or m.get("text") or ""
            if not content.strip():
                continue
            messages.append(
                NormalisedMessage(
                    role=role,
                    content=content.strip(),
                    sequence=seq,
                    message_at=_iso(m.get("created_at")),
                )
            )
        return NormalisedConversation(
            external_id=conv.get("id"),
            title=conv.get("title"),
            started_at=_iso(conv.get("created_at")),
            ended_at=_iso(conv.get("updated_at")),
            messages=messages,
        )

    def _parse_markdown(self, payload: Path) -> NormalisedConversation:
        text = payload.read_text(encoding="utf-8")
        title = payload.stem
        parts = _MD_TURN.split(text)
        messages: list[NormalisedMessage] = []
        seq = 0
        # parts looks like [preamble, 'User', body, 'Assistant', body, ...]
        for i in range(1, len(parts), 2):
            role = parts[i].lower()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not body:
                continue
            messages.append(
                NormalisedMessage(role=role, content=body, sequence=seq)
            )
            seq += 1
        return NormalisedConversation(
            external_id=None,
            title=title,
            started_at=None,
            ended_at=None,
            messages=messages,
        )
