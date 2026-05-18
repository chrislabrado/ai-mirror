"""Grok (xAI) export parser.

Handles two real-world Grok export shapes:

1. **Backend dump** (the ``prod-grok-backend.json`` file in xAI's account
   export ZIP)::

       {"conversations": [
           {"conversation": {"id", "title", "create_time", "modify_time", ...},
            "responses":    [{"response": {"_id", "sender", "message",
                                            "create_time", ...}}, ...]}
       ]}

2. **Legacy flat shape** sometimes seen in self-published Grok exports::

       {"conversations": [{"id", "title", "messages": [{"role", "content"}]}]}
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


def _iso(value: object) -> datetime | None:
    """Tolerant timestamp coercion.

    Accepts ISO-8601 strings, plain numeric epoch (seconds or millis), and
    MongoDB extended JSON: ``{"$date": "..."}`` or ``{"$date": {"$numberLong": "..."}}``.
    Returns ``None`` for any unparsable input (never raises).
    """
    if value is None or value == "":
        return None
    # MongoDB extended-JSON wrapper
    if isinstance(value, dict):
        inner = value.get("$date", value.get("date"))
        if isinstance(inner, dict):
            ms = inner.get("$numberLong") or inner.get("numberLong")
            try:
                return datetime.utcfromtimestamp(int(ms) / 1000) if ms is not None else None
            except (TypeError, ValueError):
                return None
        return _iso(inner)
    # Plain numeric
    if isinstance(value, (int, float)):
        v = float(value)
        # Heuristic: > 10^12 → millis; else seconds.
        if v > 1e12:
            v = v / 1000.0
        try:
            return datetime.utcfromtimestamp(v)
        except (OSError, OverflowError, ValueError):
            return None
    # String — ISO 8601 / RFC 3339
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            # Some Grok timestamps include nanos or trailing markers we can't parse.
            return None
    return None


def _normalise_role(raw: str | None) -> str:
    if not raw:
        return "unknown"
    s = raw.lower()
    if s in {"human", "user"}:
        return "user"
    if s in {"assistant", "agent", "model", "ai"}:
        return "assistant"
    return s


class GrokIngestor(BaseIngestor):
    source_slug = "grok"
    display_name = "Grok"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".json":
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:4096]
        # Match either the wrapped backend dump or any text mentioning xAI/Grok.
        if '"conversation":' in text and '"responses":' in text:
            return True
        if '"sender":"ASSISTANT"' in text or "'sender': 'ASSISTANT'" in text:
            return True
        return "grok" in text.lower() or '"xai"' in text.lower()

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        data = json.loads(payload.read_text(encoding="utf-8"))
        convs = data.get("conversations") if isinstance(data, dict) else data
        for conv in convs or []:
            try:
                if isinstance(conv, dict) and "conversation" in conv and "responses" in conv:
                    yield self._parse_backend_shape(conv)
                else:
                    yield self._parse_flat_shape(conv)
            except Exception:  # noqa: BLE001
                # Per-conversation failures should not abort the entire file.
                continue

    # --- shape parsers ---

    def _parse_backend_shape(self, wrapped: dict) -> NormalisedConversation:
        meta = wrapped.get("conversation") or {}
        responses = wrapped.get("responses") or []

        messages: list[NormalisedMessage] = []
        seq = 0
        for entry in responses:
            inner = entry.get("response") if isinstance(entry, dict) else None
            if not isinstance(inner, dict):
                continue
            text = inner.get("message") or inner.get("content") or ""
            if not text or not str(text).strip():
                continue
            messages.append(
                NormalisedMessage(
                    role=_normalise_role(inner.get("sender") or inner.get("role")),
                    content=str(text).strip(),
                    sequence=seq,
                    message_at=_iso(inner.get("create_time") or inner.get("timestamp")),
                    raw_metadata={"model": inner.get("model")} if inner.get("model") else None,
                )
            )
            seq += 1

        return NormalisedConversation(
            external_id=meta.get("id"),
            title=(meta.get("title") or "").strip() or None,
            started_at=_iso(meta.get("create_time")),
            ended_at=_iso(meta.get("modify_time")),
            messages=messages,
            raw_metadata={
                "user_id": meta.get("user_id"),
                "x_user_id": meta.get("x_user_id"),
                "starred": meta.get("starred"),
                "summary": (meta.get("summary") or "").strip() or None,
            },
        )

    def _parse_flat_shape(self, conv: dict) -> NormalisedConversation:
        messages: list[NormalisedMessage] = []
        for seq, msg in enumerate(conv.get("messages", []) or []):
            text = msg.get("content") or msg.get("text") or msg.get("message") or ""
            if not text or not str(text).strip():
                continue
            messages.append(
                NormalisedMessage(
                    role=_normalise_role(msg.get("role") or msg.get("sender")),
                    content=str(text).strip(),
                    sequence=seq,
                    message_at=_iso(msg.get("created_at") or msg.get("timestamp")),
                )
            )
        return NormalisedConversation(
            external_id=conv.get("id"),
            title=conv.get("title"),
            started_at=_iso(conv.get("created_at")),
            ended_at=_iso(conv.get("updated_at")),
            messages=messages,
        )
