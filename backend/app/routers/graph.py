from __future__ import annotations

from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation import Conversation, Source
from app.models.entity import Entity, Relationship
from app.models.message import Message
from app.models.report import Report, ReportBlock
from app.schemas.graph import (
    EntityDetail,
    EvidenceMessage,
    GraphPath,
    KGEdge,
    KGGraph,
    KGNode,
    NeighbourEdge,
    RelatedReport,
)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/explore", response_model=KGGraph)
async def explore_graph(
    focus: str | None = Query(
        default=None,
        description="Entity label substring. Matching entities + 1-hop neighbours are returned.",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> KGGraph:
    """Return knowledge-graph nodes and edges suitable for React Flow rendering.

    With *focus*: centre on label-matching entities plus their 1-hop neighbours.
    Without *focus*: top-N entities by salience and their mutual relationships.
    """
    entity_ids: set[int] = set()

    if focus:
        # Find entities whose label contains the focus string (case-insensitive)
        focus_result = await db.execute(
            select(Entity).where(Entity.label.ilike(f"%{focus}%")).limit(limit)
        )
        focus_entities = focus_result.scalars().all()

        if focus_entities:
            focus_ids = {e.id for e in focus_entities}

            # Gather 1-hop neighbours via Relationship table
            rel_result = await db.execute(
                select(Relationship).where(
                    or_(
                        Relationship.subject_id.in_(focus_ids),
                        Relationship.object_id.in_(focus_ids),
                    )
                ).limit(limit)
            )
            rels = rel_result.scalars().all()

            neighbour_ids: set[int] = set()
            for r in rels:
                neighbour_ids.add(r.subject_id)
                neighbour_ids.add(r.object_id)

            entity_ids = focus_ids | neighbour_ids

            # Load all relevant entities in one query
            ent_result = await db.execute(
                select(Entity).where(Entity.id.in_(entity_ids))
            )
            entities = ent_result.scalars().all()
        else:
            # Focus string matched nothing — return empty graph
            return KGGraph(nodes=[], edges=[])
    else:
        # No focus — top-N by salience
        ent_result = await db.execute(
            select(Entity).order_by(Entity.salience.desc()).limit(limit)
        )
        entities = ent_result.scalars().all()
        entity_ids = {e.id for e in entities}

        # Relationships between those entities only
        rel_result = await db.execute(
            select(Relationship).where(
                Relationship.subject_id.in_(entity_ids),
                Relationship.object_id.in_(entity_ids),
            ).limit(limit)
        )
        rels = rel_result.scalars().all()

    # Build response
    nodes = [
        KGNode(id=e.id, label=e.label, kind=e.kind, salience=e.salience)
        for e in entities
    ]
    edges = [
        KGEdge(
            id=r.id,
            source_id=r.subject_id,
            target_id=r.object_id,
            predicate=r.predicate,
            weight=r.weight,
        )
        for r in rels
    ]
    return KGGraph(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# GET /graph/node/{entity_id} — full entity detail with evidence
# ---------------------------------------------------------------------------


@router.get("/node/{entity_id}", response_model=EntityDetail)
async def get_entity_detail(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
) -> EntityDetail:
    """Return full detail for a single entity, including neighbours and evidence."""
    # Fetch the entity itself
    ent_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = ent_result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Outgoing relationships (this entity is subject)
    out_rel_result = await db.execute(
        select(Relationship, Entity)
        .join(Entity, Relationship.object_id == Entity.id)
        .where(Relationship.subject_id == entity_id)
        .order_by(Relationship.weight.desc())
        .limit(50)
    )
    outgoing: list[NeighbourEdge] = [
        NeighbourEdge(
            entity_id=obj.id,
            label=obj.label,
            kind=obj.kind,
            predicate=rel.predicate,
            weight=rel.weight,
        )
        for rel, obj in out_rel_result.all()
    ]

    # Incoming relationships (this entity is object)
    in_rel_result = await db.execute(
        select(Relationship, Entity)
        .join(Entity, Relationship.subject_id == Entity.id)
        .where(Relationship.object_id == entity_id)
        .order_by(Relationship.weight.desc())
        .limit(50)
    )
    incoming: list[NeighbourEdge] = [
        NeighbourEdge(
            entity_id=subj.id,
            label=subj.label,
            kind=subj.kind,
            predicate=rel.predicate,
            weight=rel.weight,
        )
        for rel, subj in in_rel_result.all()
    ]

    # Evidence messages — messages whose content contains the entity label
    label_lower = entity.label.lower()
    msg_result = await db.execute(
        select(Message, Conversation, Source)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(Source, Conversation.source_id == Source.id)
        .where(func.lower(Message.content).contains(label_lower))
        .order_by(Message.message_at.desc().nulls_last())
        .limit(12)
    )
    evidence_messages: list[EvidenceMessage] = []
    for msg, conv, src in msg_result.all():
        # Build a context snippet — trim to ~300 chars around first mention
        content = msg.content
        idx = content.lower().find(label_lower)
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(content), idx + 220)
            snippet = ("…" if start > 0 else "") + content[start:end].strip() + ("…" if end < len(content) else "")
        else:
            snippet = content[:300] + ("…" if len(content) > 300 else "")
        evidence_messages.append(
            EvidenceMessage(
                message_id=msg.id,
                conversation_id=conv.id,
                conversation_title=conv.title,
                source_slug=src.slug,
                role=msg.role,
                snippet=snippet,
                message_at=msg.message_at,
            )
        )

    # Related report blocks — blocks whose body_markdown contains the entity label
    block_result = await db.execute(
        select(ReportBlock, Report)
        .join(Report, ReportBlock.report_id == Report.id)
        .where(func.lower(ReportBlock.body_markdown).contains(label_lower))
        .order_by(Report.created_at.desc())
        .limit(8)
    )
    related_reports: list[RelatedReport] = []
    for block, report in block_result.all():
        body = block.body_markdown
        idx = body.lower().find(label_lower)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(body), idx + 200)
            snippet = ("…" if start > 0 else "") + body[start:end].strip() + ("…" if end < len(body) else "")
        else:
            snippet = body[:260] + ("…" if len(body) > 260 else "")
        related_reports.append(
            RelatedReport(
                report_id=report.id,
                report_kind=report.kind,
                block_type=block.block_type,
                block_heading=block.heading,
                snippet=snippet,
            )
        )

    return EntityDetail(
        id=entity.id,
        label=entity.label,
        kind=entity.kind,
        salience=entity.salience,
        description=entity.description,
        incoming=incoming,
        outgoing=outgoing,
        evidence_messages=evidence_messages,
        related_reports=related_reports,
    )


# ---------------------------------------------------------------------------
# GET /graph/path — BFS shortest path between two entities
# ---------------------------------------------------------------------------


@router.get("/path", response_model=GraphPath)
async def get_graph_path(
    from_id: int = Query(alias="from"),
    to_id: int = Query(alias="to"),
    max_hops: int = Query(default=4, ge=1, le=6),
    db: AsyncSession = Depends(get_db),
) -> GraphPath:
    """Return the shortest predicate chain (BFS) between two entities.

    Returns empty nodes/edges arrays when no path exists within *max_hops*.
    """
    if from_id == to_id:
        ent_result = await db.execute(select(Entity).where(Entity.id == from_id))
        entity = ent_result.scalar_one_or_none()
        if entity is None:
            return GraphPath(nodes=[], edges=[])
        return GraphPath(
            nodes=[KGNode(id=entity.id, label=entity.label, kind=entity.kind, salience=entity.salience)],
            edges=[],
        )

    # Load all relationships once for BFS (graph is small — 45 entities)
    all_rels_result = await db.execute(select(Relationship))
    all_rels = all_rels_result.scalars().all()

    # Build adjacency: entity_id -> list[(neighbour_id, relationship)]
    adjacency: dict[int, list[tuple[int, Relationship]]] = {}
    for rel in all_rels:
        adjacency.setdefault(rel.subject_id, []).append((rel.object_id, rel))
        adjacency.setdefault(rel.object_id, []).append((rel.subject_id, rel))

    # BFS
    visited: dict[int, tuple[int, Relationship | None]] = {from_id: (-1, None)}  # node -> (parent, edge)
    queue: deque[int] = deque([from_id])
    found = False

    while queue and not found:
        current = queue.popleft()
        depth = 0
        # Count hops back to root
        node = current
        while visited[node][0] != -1:
            node = visited[node][0]
            depth += 1
        if depth >= max_hops:
            continue
        for neighbour, rel in adjacency.get(current, []):
            if neighbour not in visited:
                visited[neighbour] = (current, rel)
                if neighbour == to_id:
                    found = True
                    break
                queue.append(neighbour)

    if not found:
        return GraphPath(nodes=[], edges=[])

    # Reconstruct path
    path_node_ids: list[int] = []
    path_rels: list[Relationship] = []
    node = to_id
    while visited[node][0] != -1:
        parent, rel = visited[node]
        path_node_ids.append(node)
        if rel is not None:
            path_rels.append(rel)
        node = parent
    path_node_ids.append(from_id)
    path_node_ids.reverse()
    path_rels.reverse()

    # Fetch entity data for path nodes
    ent_result = await db.execute(select(Entity).where(Entity.id.in_(path_node_ids)))
    entity_map = {e.id: e for e in ent_result.scalars().all()}

    nodes = [
        KGNode(id=eid, label=entity_map[eid].label, kind=entity_map[eid].kind, salience=entity_map[eid].salience)
        for eid in path_node_ids
        if eid in entity_map
    ]
    edges = [
        KGEdge(id=r.id, source_id=r.subject_id, target_id=r.object_id, predicate=r.predicate, weight=r.weight)
        for r in path_rels
    ]
    return GraphPath(nodes=nodes, edges=edges)
