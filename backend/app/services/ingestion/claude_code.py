"""Claude Code session parser.

Reads ``~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`` files. One file is
one conversation; each line is a JSON record with a ``type`` field. Real
conversation messages have ``type ∈ {user, assistant}`` and a ``message``
object with ``role`` + ``content``. Other types (snapshots, mode flips,
attachments, AI titles) are metadata we either skip or use as hints.

Content can be:
- a plain ``str`` (typically user messages typed at the prompt), or
- a ``list`` of content blocks, each with a ``type``:
    * ``text``       → flatten to its ``text`` field
    * ``tool_use``   → flatten to ``[tool: <name>] <small input preview>``
    * ``tool_result``→ flatten to ``[result: <truncated>]``
    * ``thinking``   → skipped (private chain-of-thought, not signal)
    * ``image``      → ``[image attachment]``

The flattening keeps the analytical signal (what the user asked, what the
assistant reasoned) while suppressing the noisy tool-call traffic that
would otherwise drown the corpus.
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

_REAL_MESSAGE_TYPES = frozenset({"user", "assistant"})
_TOOL_INPUT_PREVIEW_CHARS = 160
_TOOL_RESULT_PREVIEW_CHARS = 240
_MESSAGE_CONTENT_MAX = 8000  # trim absurdly long messages so embeddings stay fast


def _iso(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _flatten_content(content: object) -> str:
    """Reduce Claude Code's structured content to a single text payload."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
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
                parts.append(text.strip())
        elif btype == "tool_use":
            name = block.get("name") or "?"
            raw_input = block.get("input")
            try:
                input_preview = (
                    json.dumps(raw_input, ensure_ascii=False)
                    if raw_input is not None
                    else ""
                )
            except (TypeError, ValueError):
                input_preview = str(raw_input)
            input_preview = input_preview[:_TOOL_INPUT_PREVIEW_CHARS]
            parts.append(f"[tool: {name}] {input_preview}".strip())
        elif btype == "tool_result":
            inner = block.get("content")
            if isinstance(inner, list):
                inner_text = " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in inner
                )
            else:
                inner_text = str(inner) if inner is not None else ""
            inner_text = inner_text.strip()[:_TOOL_RESULT_PREVIEW_CHARS]
            if inner_text:
                parts.append(f"[result: {inner_text}]")
        elif btype == "image":
            parts.append("[image attachment]")
        elif btype == "thinking":
            # Extended thinking — skip from analysis corpus.
            continue
        # Unknown block types are silently ignored.

    return "\n\n".join(p for p in parts if p).strip()


class ClaudeCodeIngestor(BaseIngestor):
    source_slug = "claude_code"
    display_name = "Claude Code"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        if payload.suffix.lower() != ".jsonl":
            return False
        # Claude Code session files have a distinctive set of fields on the
        # very first line: sessionId + (permissionMode | type | etc).
        text = raw_text or payload.read_text(encoding="utf-8", errors="ignore")[:2048]
        first_line = text.splitlines()[0] if text else ""
        if '"sessionId"' in first_line and (
            '"permissionMode"' in first_line
            or '"type":"summary"' in first_line
            or '"parentUuid"' in first_line
        ):
            return True
        return False

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        # One JSONL file = one conversation.
        try:
            yield self._parse_session(payload)
        except Exception:  # noqa: BLE001
            return

    def _parse_session(self, payload: Path) -> NormalisedConversation:
        session_id: str | None = None
        cwd: str | None = None
        git_branch: str | None = None
        ai_title: str | None = None
        first_prompt: str | None = None
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
            session_id = session_id or obj.get("sessionId")
            cwd = cwd or obj.get("cwd")
            git_branch = git_branch or obj.get("gitBranch")

            if t == "ai-title":
                title_val = obj.get("aiTitle")
                if isinstance(title_val, str) and title_val.strip():
                    ai_title = title_val.strip()
                continue
            if t == "last-prompt":
                lp = obj.get("lastPrompt")
                if isinstance(lp, str) and lp.strip() and not first_prompt:
                    first_prompt = lp.strip()
                continue
            if t not in _REAL_MESSAGE_TYPES:
                continue

            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue

            body = _flatten_content(message.get("content"))
            if not body:
                continue
            if len(body) > _MESSAGE_CONTENT_MAX:
                body = body[:_MESSAGE_CONTENT_MAX] + " …[truncated]"

            ts = _iso(obj.get("timestamp"))
            if ts is not None:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts

            if role == "user" and not first_prompt:
                first_prompt = body[:200]

            messages.append(
                NormalisedMessage(
                    role=role,
                    content=body,
                    sequence=seq,
                    message_at=ts,
                    raw_metadata={
                        "uuid": obj.get("uuid"),
                        "parentUuid": obj.get("parentUuid"),
                    },
                )
            )
            seq += 1

        # Title preference: AI-generated title > first user prompt snippet > sessionId fragment
        title = ai_title or (first_prompt[:80] + ("…" if first_prompt and len(first_prompt) > 80 else "") if first_prompt else None)
        if not title:
            title = f"CC session {(session_id or payload.stem)[:8]}"

        # External id MUST be unique per file. Sub-agent runs share the
        # parent session's `sessionId` (Claude Code writes one JSONL per
        # spawned agent), so keying on session_id alone collapses 207
        # files into 31 conversations. Compose with the filename to keep
        # them separate.
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
                "git_branch": git_branch,
                "session_file": payload.name,
            },
        )
