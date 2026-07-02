from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SourceSlug = Literal[
    "chatgpt",
    "claude",
    "claude_code",
    "openclaw",
    "grok",
    "gemini",
    "perplexity",
    "local",
    "auto",
]


class IngestRequest(BaseModel):
    """Companion payload for an upload — sent as a multipart form field."""

    source: SourceSlug = "auto"
    label: str | None = None


RemoteConnector = Literal["claude_code", "openclaw", "path"]


class RemoteIngestRequest(BaseModel):
    """Payload for /ingest/remote — pull conversations straight from disk."""

    connector: RemoteConnector
    path: str | None = None
    since: datetime | None = None
    limit: int | None = None
    label: str | None = None


class IngestResponse(BaseModel):
    job_id: int
    source: str
    filename: str
    status: str
    conversations_imported: int
    messages_imported: int
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
