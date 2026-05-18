from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class NormalisedMessage:
    role: str  # user | assistant | system | tool
    content: str
    sequence: int
    message_at: datetime | None = None
    raw_metadata: dict[str, Any] | None = None


@dataclass
class NormalisedConversation:
    external_id: str | None
    title: str | None
    started_at: datetime | None
    ended_at: datetime | None
    messages: list[NormalisedMessage] = field(default_factory=list)
    raw_metadata: dict[str, Any] | None = None


class BaseIngestor:
    """Abstract base for platform-specific parsers."""

    source_slug: str = ""
    display_name: str = ""

    def detect(self, payload: Path, raw_text: str | None = None) -> bool:  # noqa: ARG002
        """Return True if this parser recognises the payload format."""
        return False

    def parse(self, payload: Path) -> Iterable[NormalisedConversation]:
        raise NotImplementedError
