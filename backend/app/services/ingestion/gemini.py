"""Gemini (Google) export parser.

Handles three real-world Gemini export shapes:

1. **Google Takeout — *Gemini Apps Activity* HTML** (the format users actually
   get when ticking the right Takeout product). One ``<div class="outer-cell">``
   per Gemini interaction; the inner ``content-cell`` divs hold the user query
   and the Gemini response with a timestamp.

2. **Google Takeout — JSON ``activity.json``** (less common; appears when a
   user selects JSON as the Takeout output format). Top-level list of records
   with ``title`` ("You said X") and ``description`` (Gemini response).

3. **Modern Gemini chat JSON** with ``{conversations: [{turns: [...]}]}`` —
   what some self-hosted exporters produce.
"""
from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from app.services.ingestion.base import (
    BaseIngestor,
    NormalisedConversation,
    NormalisedMessage,
)


def _normalize_ws(value: str) -> str:
    """Replace U+202F (narrow no-break) and U+00A0 with ASCII space."""
    return value.replace(" ", " ").replace(" ", " ")


def _iso(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = _normalize_ws(value).strip()
        # Try ISO 8601 first.
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Takeout: "May 17, 2026, 1:23:45 PM EDT". `%Z` is unreliable on slim
        # Linux (no tzdata abbreviations), so strip the trailing TZ manually.
        value = re.sub(r"\s+[A-Z]{2,5}$", "", value)
        for fmt in (
            "%b %d, %Y, %I:%M:%S %p %Z",  # narrow no-break space (recent Takeout)
            "%b %d, %Y, %I:%M:%S %p %Z",
            "%b %d, %Y, %I:%M:%S %p",
            "%b %d, %Y, %I:%M:%S %p",
        ):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
    return None


# ----------------------------------------------------------------------------
# HTML parser — Takeout MyActivity / Gemini Apps Activity
# ----------------------------------------------------------------------------


_VOID_TAGS: frozenset[str] = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    ]
)


class _OuterCellExtractor(HTMLParser):
    """Streaming HTML parser. Emits one record per ``outer-cell`` div.

    Each record contains ``contents`` (list of text blocks from each
    content-cell child). The first content block is the user query; the
    second is Gemini's response (when present). The timestamp lives at the
    end of the first block.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[dict] = []
        self._stack: list[str] = []  # active non-void tag stack
        self._outer_depth: int | None = None
        self._content_depth: int | None = None
        self._cur_record: dict | None = None
        self._cur_content_chunks: list[str] = []
        self._capturing: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID_TAGS:
            if self._capturing and tag == "br":
                self._cur_content_chunks.append("\n")
            return
        self._stack.append(tag)
        depth = len(self._stack)
        attr_map = dict(attrs)
        cls = attr_map.get("class") or ""
        if "outer-cell" in cls and self._outer_depth is None:
            self._outer_depth = depth
            self._cur_record = {"contents": []}
        elif (
            self._outer_depth is not None
            and "content-cell" in cls
            and "mdl-typography--text-right" not in cls
            and self._content_depth is None
        ):
            self._content_depth = depth
            self._cur_content_chunks = []
            self._capturing = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Self-closing void elements (rare in Takeout HTML, but safe to handle).
        if self._capturing and tag == "br":
            self._cur_content_chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        depth = len(self._stack)
        # Close content-cell first.
        if self._content_depth is not None and depth == self._content_depth:
            text = "".join(self._cur_content_chunks).strip()
            if text and self._cur_record is not None:
                self._cur_record["contents"].append(text)
            self._content_depth = None
            self._capturing = False
            self._cur_content_chunks = []
        # Close outer-cell.
        if self._outer_depth is not None and depth == self._outer_depth:
            if self._cur_record and self._cur_record.get("contents"):
                self.records.append(self._cur_record)
            self._cur_record = None
            self._outer_depth = None
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        else:
            # Tolerant of malformed HTML — try to pop the matching tag.
            for i in range(len(self._stack) - 1, -1, -1):
                if self._stack[i] == tag:
                    del self._stack[i:]
                    break

    def handle_data(self, data: str) -> None:
        if self._capturing and data:
            self._cur_content_chunks.append(data)


_GEMINI_PRODUCT_NAMES = ("Gemini Apps", "Gemini", "Bard")


# Pre-compiled timestamp matcher for Takeout's "Mon DD, YYYY, H:MM:SS XM TZ" format.
# Tolerant of Unicode narrow / non-breaking spaces (U+202F, U+00A0) between
# the time and the AM/PM marker.
_TS_LINE = re.compile(
    r"^[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2}(?::\d{2})?[\s  ]+[AP]M"
    r"(?:[\s  ]+[A-Z]{2,5})?$"
)
# Strip the Takeout prefix that labels the user-query line; the prefix may use
# a non-breaking space ( ) instead of a regular space.
_PROMPT_PREFIX_RE = re.compile(
    r"^(Prompted|Asked|Searched|Said to)\s*"
    r"(?:Gemini\s*Apps|Gemini|gemini\s*apps|gemini)?"
    r"[\s ]+",
    re.IGNORECASE,
)


def _strip_prompt_prefix(line: str) -> str:
    return _PROMPT_PREFIX_RE.sub("", line, count=1)


def _split_user_assistant(lines: list[str]) -> tuple[str, str, datetime | None]:
    """Split a Takeout content-cell into (user_text, assistant_text, timestamp).

    Lines before the timestamp belong to the user prompt; lines after belong
    to Gemini's response. If no timestamp is found, all lines are treated as
    the user prompt (Takeout occasionally omits timestamps).
    """
    ts: datetime | None = None
    ts_index: int | None = None
    for i, ln in enumerate(lines):
        if _TS_LINE.match(ln):
            parsed = _iso(ln)
            if parsed:
                ts = parsed
                ts_index = i
                break

    if ts_index is None:
        user_lines = lines
        assistant_lines: list[str] = []
    else:
        user_lines = lines[:ts_index]
        assistant_lines = lines[ts_index + 1 :]

    # Strip "Attached N files." lines and the link rows that follow.
    def _clean(ls: list[str]) -> list[str]:
        out: list[str] = []
        for ln in ls:
            if ln.startswith("Attached ") and "file" in ln:
                continue
            if ln.startswith("- ") and len(ln) < 200:
                # Likely an attachment filename row.
                continue
            out.append(ln)
        return out

    user_lines = _clean(user_lines)
    assistant_lines = _clean(assistant_lines)

    # Strip prompt prefix from the first user line.
    if user_lines:
        user_lines[0] = _strip_prompt_prefix(user_lines[0])

    user_text = "\n".join(user_lines).strip()
    assistant_text = "\n".join(assistant_lines).strip()
    return user_text, assistant_text, ts


def _parse_takeout_html(path: Path) -> list[NormalisedConversation]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    parser = _OuterCellExtractor()
    parser.feed(raw)

    conversations: list[NormalisedConversation] = []
    for idx, rec in enumerate(parser.records):
        contents: list[str] = rec.get("contents") or []
        if not contents:
            continue

        # Takeout's Gemini Apps export puts the entire (prompt + response)
        # interaction inside the first content-cell, with subsequent cells
        # holding metadata (attachments, product labels). Process the first
        # cell as a 2-message conversation; ignore the rest.
        first = _normalize_ws(contents[0])
        lines = [ln.strip() for ln in first.split("\n") if ln.strip()]
        if not lines:
            continue

        user_text, assistant_text, ts = _split_user_assistant(lines)

        messages: list[NormalisedMessage] = []
        if user_text:
            messages.append(
                NormalisedMessage(
                    role="user",
                    content=user_text,
                    sequence=0,
                    message_at=ts,
                )
            )
        if assistant_text:
            messages.append(
                NormalisedMessage(
                    role="assistant",
                    content=assistant_text,
                    sequence=len(messages),
                    message_at=ts,
                )
            )
        if not messages:
            continue

        title_src = user_text or assistant_text
        title = title_src[:80] + ("…" if len(title_src) > 80 else "")
        conversations.append(
            NormalisedConversation(
                external_id=f"takeout-html-{idx}",
                title=title,
                started_at=ts,
                ended_at=ts,
                messages=messages,
            )
        )
    return conversations


# ----------------------------------------------------------------------------
# JSON parsers (Takeout activity.json, modern self-hosted format)
# ----------------------------------------------------------------------------


def _parse_takeout_activity_json(data: list) -> list[NormalisedConversation]:
    convs: list[NormalisedConversation] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        product_titles = [(h or {}).get("name", "") for h in entry.get("header", []) if isinstance(h, dict)]
        product = entry.get("header") or entry.get("product") or ""
        if isinstance(product, list):
            product = " ".join(str(p) for p in product)
        product = str(product) + " " + " ".join(product_titles)
        if not any(name.lower() in product.lower() for name in _GEMINI_PRODUCT_NAMES):
            continue
        title = entry.get("title") or ""
        description = entry.get("description") or ""
        ts = _iso(entry.get("time"))
        msgs: list[NormalisedMessage] = []
        if title.strip():
            msgs.append(NormalisedMessage(role="user", content=title.strip(), sequence=0, message_at=ts))
        if description.strip():
            msgs.append(NormalisedMessage(role="assistant", content=description.strip(), sequence=len(msgs), message_at=ts))
        if not msgs:
            continue
        convs.append(
            NormalisedConversation(
                external_id=f"takeout-json-{idx}",
                title=title[:80] or None,
                started_at=ts,
                ended_at=ts,
                messages=msgs,
            )
        )
    return convs


def _parse_modern_chat_json(data: dict) -> list[NormalisedConversation]:
    convs_raw = data.get("conversations") if isinstance(data, dict) else data
    out: list[NormalisedConversation] = []
    for conv in convs_raw or []:
        turns = conv.get("turns") or conv.get("messages") or []
        msgs: list[NormalisedMessage] = []
        for seq, t in enumerate(turns):
            role = t.get("role") or ("user" if t.get("user_query") else "assistant")
            text = t.get("text") or t.get("content") or t.get("user_query") or t.get("response") or ""
            if not text or not str(text).strip():
                continue
            msgs.append(
                NormalisedMessage(
                    role=role,
                    content=str(text).strip(),
                    sequence=seq,
                    message_at=_iso(t.get("timestamp")),
                )
            )
        if not msgs:
            continue
        out.append(
            NormalisedConversation(
                external_id=conv.get("id"),
                title=conv.get("title"),
                started_at=_iso(conv.get("created_at")),
                ended_at=_iso(conv.get("updated_at")),
                messages=msgs,
            )
        )
    return out


# ----------------------------------------------------------------------------
# Ingestor
# ----------------------------------------------------------------------------


class GeminiIngestor(BaseIngestor):
    source_slug = "gemini"
    display_name = "Gemini"

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:
        suffix = payload.suffix.lower()
        if suffix not in {".html", ".htm", ".json"}:
            return False
        # Takeout's MyActivity.html files put CSS first; the conversation
        # markup starts well past 8 KB. Sniff a larger window.
        if raw_text is not None:
            text = raw_text
        else:
            try:
                with payload.open("r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(262_144)  # 256 KB head
            except OSError:
                return False
        haystack = text.lower()
        if "gemini" in haystack or "bard" in haystack:
            return True
        if suffix in {".html", ".htm"} and 'class="outer-cell' in text:
            return True
        return '"turns"' in text and suffix == ".json"

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        suffix = payload.suffix.lower()
        if suffix in {".html", ".htm"}:
            yield from _parse_takeout_html(payload)
            return

        # JSON
        data = json.loads(payload.read_text(encoding="utf-8"))
        if isinstance(data, list):
            yield from _parse_takeout_activity_json(data)
            return
        if isinstance(data, dict):
            yield from _parse_modern_chat_json(data)


# Re-export for backwards compatibility.
_html = html  # silence unused-import lint while keeping html available for future use
