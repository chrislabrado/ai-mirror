from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KGNode(BaseModel):
    id: int
    label: str
    kind: str
    salience: float


class KGEdge(BaseModel):
    id: int
    source_id: int
    target_id: int
    predicate: str
    weight: float


class KGGraph(BaseModel):
    nodes: list[KGNode]
    edges: list[KGEdge]


# ---------------------------------------------------------------------------
# Entity detail — returned by GET /graph/node/{entity_id}
# ---------------------------------------------------------------------------


class NeighbourEdge(BaseModel):
    entity_id: int
    label: str
    kind: str
    predicate: str
    weight: float


class EvidenceMessage(BaseModel):
    message_id: int
    conversation_id: int
    conversation_title: str | None
    source_slug: str
    role: str
    snippet: str
    message_at: datetime | None


class RelatedReport(BaseModel):
    report_id: int
    report_kind: str
    block_type: str
    block_heading: str | None
    snippet: str


class EntityDetail(BaseModel):
    id: int
    label: str
    kind: str
    salience: float
    description: str | None
    incoming: list[NeighbourEdge]
    outgoing: list[NeighbourEdge]
    evidence_messages: list[EvidenceMessage]
    related_reports: list[RelatedReport]


# ---------------------------------------------------------------------------
# Shortest path — returned by GET /graph/path
# ---------------------------------------------------------------------------


class GraphPath(BaseModel):
    nodes: list[KGNode]
    edges: list[KGEdge]
