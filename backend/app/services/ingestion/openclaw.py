"""OpenClaw session parser.

Reads ``~/.openclaw/agents/<id>/sessions/<uuid>.jsonl`` files (session
format v3). One file is one conversation; each line is a JSON record with
a ``type`` field:

- ``session``  → header line: ``{"type":"session","version":3,"id":"<uuid>",
  "timestamp":"ISO","cwd":...}``
- ``message``  → ``{"type":"message","timestamp":"ISO","message":{"role":
  "user"|"assistant","content":[{"type":"text","text":...}],
  "timestamp":<ms epoch>}}``
- everything else (``model_change``, ``thinking_level_change``, ``custom``,
  …) is skipped.

Content blocks observed in real sessions: ``text`` (flattened),
``toolCall`` (reduced to a short bracketed placeholder), ``thinking``
(skipped). Messages with role ``toolResult`` are tool traffic, not
conversation, and are skipped.

OpenClaw injects a timestamp prefix like ``[Fri 2026-04-03 11:39 EDT] ``
into user texts; we strip it so the corpus holds what the user actually
said.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from app.services.ingestion.base import (
    BaseIngestor,
    NormalisedConversation,
    NormalisedMessage,
)

_TOOL_INPUT_PREVIEW_CHARS = 160
_MESSAGE_CONTENT_MAX = 8000  # trim absurdly long messages so embeddings stay fast
_TITLE_MAX = 60

# Injected leading timestamp on user texts, e.g. "[Fri 2026-04-03 11:39 EDT] ".
_USER_TS_PREFIX = re.compile(r"^\[\w{3} \d{4}-\d{2}-\d{2} [\d:]+ [A-Z]{2,4}\]\s*")


def _iso(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ms_epoch(value: object) -> datetime | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _flatten_content(content: object, *, role: str) -> str:
    """Reduce OpenClaw's structured content to a single text payload."""
    if content is None:
        return ""
    if isinstance(content, str):
        text = content.strip()
        return _USER_TS_PREFIX.sub("", text) if role == "user" else text
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            if isinstance(block, str) and block.strip():
                parts.append(block.strip())
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                text = text.strip()
                if role == "user":
                    text = _USER_TS_PREFIX.sub("", text)
                if text:
                    parts.append(text)
        elif btype == "toolCall":
            name = block.get("name") or "?"
            raw_args = block.get("arguments")
            try:
                args_preview = (
                    json.dumps(raw_args, ensure_ascii=False)
                    if raw_args is not None
                    else ""
                )
            except (TypeError, ValueError):
                args_preview = str(raw_args)
            args_preview = args_preview[:_TOOL_INPUT_PREVIEW_CHARS]
            parts.append(f"[tool: {name}] {args_preview}".strip())
        elif btype == "image":
            parts.append("[image attachment]")
        elif btype == "thinking":
            # Extended thinking — skip from analysis corpus.
            continue
        # Unknown block types are silently ignored.

    return "\n\n".join(p for p in parts if p).strip()


class OpenClawIngestor(BaseIngestor):
    source_slug = "openclaw"
    display_name = "OpenClaw"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".jsonl":
            return False
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:2048]
        first_line = text.splitlines()[0] if text else ""
        return '"type":"session"' in first_line and '"version"' in first_line

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        # One JSONL file = one conversation.
        try:
            yield self._parse_session(payload)
        except Exception:  # noqa: BLE001
            return

    def _parse_session(self, payload: Path) -> NormalisedConversation:
        session_id: str | None = None
        cwd: str | None = None
        first_user_text: str | None = None
        messages: list[NormalisedMessage] = []
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        seq = 0

        for raw_line in payload.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            t = obj.get("type")
            if t == "session":
                sid = obj.get("id")
                if isinstance(sid, str) and sid:
                    session_id = session_id or sid
                cwd_val = obj.get("cwd")
                if isinstance(cwd_val, str) and cwd_val:
                    cwd = cwd or cwd_val
                continue
            if t != "message":
                # model_change / thinking_level_change / custom / … — metadata.
                continue

            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role not in {"user", "assistant"}:
                # toolResult traffic and anything exotic is not conversation.
                continue

            body = _flatten_content(message.get("content"), role=role)
            if not body:
                continue
            if len(body) > _MESSAGE_CONTENT_MAX:
                body = body[:_MESSAGE_CONTENT_MAX] + " …[truncated]"

            ts = _iso(obj.get("timestamp")) or _ms_epoch(message.get("timestamp"))
            if ts is not None:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts

            if role == "user" and not first_user_text:
                first_user_text = body

            messages.append(
                NormalisedMessage(
                    role=role,
                    content=body,
                    sequence=seq,
                    message_at=ts,
                    raw_metadata={
                        "id": obj.get("id"),
                        "parentId": obj.get("parentId"),
                    },
                )
            )
            seq += 1

        if first_user_text:
            title = first_user_text[:_TITLE_MAX] + (
                "…" if len(first_user_text) > _TITLE_MAX else ""
            )
        else:
            title = f"OpenClaw session {(session_id or payload.stem)[:8]}"

        external_id = (
            f"{session_id}:{payload.stem}" if session_id else payload.stem
        )
        return NormalisedConversation(
            external_id=external_id,
            title=title,
            started_at=first_ts,
            ended_at=last_ts,
            messages=messages,
            raw_metadata={
                "cwd": cwd,
                "session_file": payload.name,
            },
        )
