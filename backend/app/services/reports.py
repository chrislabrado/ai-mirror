"""Report generation services (Full Mirror, Advanced Abstract, Focus Lens).

The blocks below are the canonical section list from the v1.1 spec.
Each block is persisted as a :class:`ReportBlock` row so the UI can
render modular cards and the analysis pipeline can re-use blocks
across reports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation, Source
from app.models.entity import Entity, Relationship
from app.models.message import Message
from app.models.report import Report, ReportBlock
from app.schemas.common import Evidence, GaugeSet, ReportBlockOut
from app.schemas.focus_lens import FocusLensRequest, FocusLensResponse
from app.schemas.insights import DeepDiveRequest, DeepDiveResponse
from app.schemas.reports import ReportRequest, ReportResponse
from app.services.llm import LLMUnavailable, chat_json, llm_available
from app.utils.logger import get_logger

log = get_logger(__name__)

_VALID_ENTITY_KINDS = frozenset(
    {"concept", "person", "tool", "project", "belief", "trait", "source", "topic"}
)


def _coerce_structured(value: object) -> dict[str, object] | None:
    """LLMs sometimes return ``structured`` as a string/list — coerce to dict-or-None."""
    if isinstance(value, dict):
        return value
    if value is None or value == "":
        return None
    # Wrap non-dict so the data isn't lost.
    return {"value": value}


def _coerce_evidence(value: object) -> list[dict[str, object]] | None:
    """LLMs sometimes return ``evidence`` as a string. Normalise to list-or-None."""
    if isinstance(value, list):
        # Each element should be a dict; wrap strings.
        cleaned: list[dict[str, object]] = []
        for item in value:
            if isinstance(item, dict):
                cleaned.append(item)
            elif isinstance(item, str) and item.strip():
                cleaned.append({"snippet": item.strip()})
        return cleaned or None
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [{"snippet": value.strip()}] if value.strip() else None
    return None


async def _persist_knowledge_graph(
    db: AsyncSession,
    kg_data: object,
) -> tuple[int, int]:
    """Upsert entities and relationships extracted from the LLM knowledge graph.

    Returns (entity_upserted_count, relationship_upserted_count).
    Skips malformed records defensively rather than raising.
    """
    from app.services.knowledge_graph import upsert_triple

    if not isinstance(kg_data, dict):
        return 0, 0

    raw_entities: object = kg_data.get("entities")
    raw_rels: object = kg_data.get("relationships")

    if not isinstance(raw_entities, list):
        return 0, 0

    # --- Upsert entities ---
    entity_label_to_id: dict[str, int] = {}
    entity_upserted = 0

    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        kind = item.get("kind")
        if not isinstance(label, str) or not label.strip():
            continue
        label = label.strip()
        if not isinstance(kind, str) or kind not in _VALID_ENTITY_KINDS:
            kind = "concept"

        try:
            salience_raw = item.get("salience", 0.0)
            salience = float(salience_raw) if isinstance(salience_raw, (int, float)) else 0.0
            salience = max(0.0, min(1.0, salience))
        except (TypeError, ValueError):
            salience = 0.0

        description = item.get("description")
        if not isinstance(description, str):
            description = None

        # Check for existing entity keyed by (label, kind)
        existing_result = await db.execute(
            select(Entity).where(Entity.label == label, Entity.kind == kind).limit(1)
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            # Update salience to max; fill blank description
            existing.salience = max(existing.salience, salience)
            if not existing.description and description:
                existing.description = description
            entity_label_to_id[label] = existing.id
        else:
            new_entity = Entity(
                label=label,
                kind=kind,
                salience=salience,
                description=description,
            )
            db.add(new_entity)
            await db.flush()
            entity_label_to_id[label] = new_entity.id
            entity_upserted += 1

    # Also record updates to existing entities as upserts
    # (count them only on true inserts to keep the log meaningful)

    # --- Upsert relationships ---
    rel_upserted = 0

    if not isinstance(raw_rels, list):
        raw_rels = []

    for item in raw_rels:
        if not isinstance(item, dict):
            continue
        subject_label = item.get("subject")
        object_label = item.get("object")
        predicate = item.get("predicate")

        if (
            not isinstance(subject_label, str)
            or not isinstance(object_label, str)
            or not isinstance(predicate, str)
        ):
            continue

        subject_label = subject_label.strip()
        object_label = object_label.strip()
        predicate = predicate.strip()

        if not subject_label or not object_label or not predicate:
            continue

        subject_id = entity_label_to_id.get(subject_label)
        object_id = entity_label_to_id.get(object_label)
        if subject_id is None or object_id is None:
            continue

        try:
            weight_raw = item.get("weight", 1.0)
            weight = float(weight_raw) if isinstance(weight_raw, (int, float)) else 1.0
            weight = max(0.0, min(1.0, weight))
        except (TypeError, ValueError):
            weight = 1.0

        # Dedup on (subject_id, object_id, predicate)
        existing_rel_result = await db.execute(
            select(Relationship).where(
                Relationship.subject_id == subject_id,
                Relationship.object_id == object_id,
                Relationship.predicate == predicate,
            ).limit(1)
        )
        existing_rel = existing_rel_result.scalar_one_or_none()

        if existing_rel is not None:
            existing_rel.weight = max(existing_rel.weight, weight)
        else:
            new_rel = Relationship(
                subject_id=subject_id,
                object_id=object_id,
                predicate=predicate,
                weight=weight,
            )
            db.add(new_rel)
            rel_upserted += 1

        # Mirror to Neo4j — silent on failure
        try:
            upsert_triple(subject_label, predicate, object_label, weight=weight)
        except Exception:  # noqa: BLE001
            pass

    await db.flush()
    return entity_upserted, rel_upserted


FULL_MIRROR_BLOCKS: list[tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("cognitive_style", "Cognitive Style"),
    ("strengths", "Strengths"),
    ("weaknesses", "Weaknesses"),
    ("psychology", "Psychological Profile"),
    ("neurodivergence_signals", "Neurodivergence Signals"),
    ("aptitudes", "Aptitudes"),
    ("recurring_themes", "Recurring Themes"),
    ("growth_arc", "Growth Arc Over Time"),
    ("blind_spots", "Blind Spots"),
    ("actionable_insights", "Actionable Insights"),
]

ABSTRACT_BLOCKS: list[tuple[str, str]] = [
    ("meta_pattern_synthesis", "Meta-Pattern Synthesis"),
    ("conceptual_lattice", "Conceptual Lattice"),
    ("philosophical_signature", "Philosophical Signature"),
    ("inner_dialogue_motifs", "Inner Dialogue Motifs"),
    ("symbolic_compression", "Symbolic Compression"),
]


async def _gather_corpus(db: AsyncSession, request: ReportRequest) -> str:
    """Lightweight corpus assembly — last N messages, optionally date-bounded."""
    stmt = select(Message).order_by(Message.message_at.desc().nullslast(), Message.id.desc()).limit(400)
    if request.date_from:
        stmt = stmt.where(Message.message_at >= request.date_from)
    if request.date_to:
        stmt = stmt.where(Message.message_at <= request.date_to)
    rows = (await db.execute(stmt)).scalars().all()
    return "\n\n---\n\n".join(f"[{m.role}] {m.content[:1200]}" for m in rows)


def _placeholder_blocks(blocks: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "block_type": slug,
            "heading": heading,
            "body_markdown": (
                f"## {heading}\n\n"
                "_LLM not configured — this is a placeholder. Configure "
                "`LLM_PROVIDER` and an API key (or run the `local-llm` profile) "
                "to populate this section._"
            ),
            "structured": None,
            "evidence": [],
        }
        for slug, heading in blocks
    ]


async def _generate_report(
    db: AsyncSession,
    kind: str,
    title_prefix: str,
    blocks: list[tuple[str, str]],
    request: ReportRequest,
    system_prompt: str,
    *,
    extract_kg: bool = False,
) -> ReportResponse:
    import time as _time

    started = _time.monotonic()
    corpus = await _gather_corpus(db, request)
    title = f"{title_prefix} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    log.info(
        "report.start",
        extra={
            "kind": kind,
            "corpus_chars": len(corpus),
            "block_count_expected": len(blocks),
            "llm_available": llm_available(),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        },
    )

    if llm_available() and corpus.strip():
        try:
            log.info(
                "report.llm_requested",
                extra={"kind": kind, "provider": settings.llm_provider, "model": settings.llm_model},
            )
            llm_started = _time.monotonic()

            kg_instruction = ""
            if extract_kg:
                kg_instruction = (
                    "\n- knowledge_graph: REQUIRED rich object with:\n"
                    "    - entities: array — MUST contain BETWEEN 40 AND 80 entries (less than 40 is "
                    "considered a failure). Cover broad ground across the corpus: include people the "
                    "user mentions, every distinct tool / framework / SDK referenced, every project, "
                    "every recurring concept, every belief or value the user expresses, every trait "
                    "or pattern, every source platform, every topic of sustained interest.\n"
                    "      Each entity object: {label, kind, salience, description}\n"
                    "      - label: short noun phrase (e.g. 'Knowledge Graph', 'Dynatrace', 'Chris')\n"
                    "      - kind: one of concept | person | tool | project | belief | trait | source | topic\n"
                    "      - salience: float in [0,1] — how central this entity is to the user's thinking\n"
                    "      - description: 1-2 sentence factual context grounded in the corpus\n"
                    "    - relationships: array — CRITICAL DENSITY REQUIREMENT. MUST contain AT LEAST "
                    "TWO RELATIONSHIPS PER ENTITY on average. If you emit 50 entities, emit AT LEAST "
                    "100 relationships. If you emit 60 entities, emit AT LEAST 120. EVERY entity MUST "
                    "appear in at least one relationship — orphaned entities are forbidden. Aim for "
                    "1.5×–2.5× the entity count.\n"
                    "      Each relationship object: {subject, predicate, object, weight}\n"
                    "      - subject and object MUST exactly match labels from the entities array\n"
                    "      - predicate: snake_case verb phrase (e.g. 'is_building', 'depends_on',\n"
                    "        'critiques', 'uses', 'is_motivated_by', 'has_aptitude_in', 'frustrated_by',\n"
                    "        'is_a', 'leverages', 'reflects_on', 'contrasts_with', 'inspired_by',\n"
                    "        'is_blocked_by', 'co-occurs_with', 'is_an_instance_of')\n"
                    "      - weight: float in [0,1] — strength of the relationship\n"
                    "    Required edge patterns to ensure connectivity (in addition to anything "
                    "domain-specific you find):\n"
                    "      * connect every tool, project, and source to the person who uses them\n"
                    "      * connect every belief and trait to the person who holds them\n"
                    "      * connect every concept to at least one project, tool, or other concept "
                    "        that it relates to\n"
                    "      * connect every topic to at least one related concept or source\n"
                    "    Prioritise BREADTH over depth. Do not over-cluster around a single topic.\n"
                )

            payload = await chat_json(
                system=system_prompt,
                user=(
                    "Analyse the following normalised AI conversation excerpts and "
                    "produce a structured JSON object containing:\n"
                    "- summary: 4-5 concise bullet observations (one string per bullet, "
                    "joined by newlines)\n"
                    "- gauges: {thought_clarity, self_reflection_depth, aptitude_balance} "
                    "each a float between 0 and 1\n"
                    "- blocks: array of {block_type, heading, body_markdown, structured, evidence}"
                    + kg_instruction
                    + f"\n\nExpected block_types in order: {[b[0] for b in blocks]}\n\n"
                    f"CORPUS:\n{corpus[:60000]}"
                ),
                temperature=0.3,
                # Higher cap for Full Mirror w/ KG extraction (11 blocks + 25-60 entities + 30-80 edges).
                max_tokens=16384 if extract_kg else 4096,
            )
            llm_duration = round(_time.monotonic() - llm_started, 2)
            log.info(
                "report.llm_responded",
                extra={
                    "kind": kind,
                    "duration_seconds": llm_duration,
                    "summary_chars": len(str(payload.get("summary", ""))),
                    "blocks_received": len(payload.get("blocks") or []),
                },
            )
            summary = payload.get("summary", "").strip()
            gauges_data = payload.get("gauges") or None
            llm_blocks = payload.get("blocks") or _placeholder_blocks(blocks)

            # Persist knowledge graph (Full Mirror only)
            if extract_kg:
                kg_raw = payload.get("knowledge_graph")
                if kg_raw is not None:
                    log.info("kg.extracted", extra={"has_data": bool(kg_raw)})
                    try:
                        ent_count, rel_count = await _persist_knowledge_graph(db, kg_raw)
                        log.info(
                            "kg.entity_upserted",
                            extra={"entity_count": ent_count},
                        )
                        log.info(
                            "kg.relationship_upserted",
                            extra={"relationship_count": rel_count},
                        )
                    except Exception as kg_exc:  # noqa: BLE001
                        log.warning("kg.persistence_failed", extra={"error": str(kg_exc)})

        except (LLMUnavailable, Exception) as exc:  # noqa: BLE001
            log.warning("report.llm_failed", extra={"kind": kind, "error": str(exc)})
            summary = "LLM call failed — placeholder content rendered."
            gauges_data = None
            llm_blocks = _placeholder_blocks(blocks)
    else:
        summary = (
            "• Ingest data first or configure an LLM to populate this report.\n"
            "• Open the Export Guide for per-platform extraction steps.\n"
            "• Reports are stored as modular JSON blocks for reuse."
        )
        gauges_data = None
        llm_blocks = _placeholder_blocks(blocks)

    report = Report(
        kind=kind,
        title=title,
        query=request.notes,
        summary=summary,
        gauges=gauges_data,
        model_used=f"{settings.llm_provider}:{settings.llm_model}" if llm_available() else None,
    )
    db.add(report)
    await db.flush()

    inserted_blocks: list[ReportBlock] = []
    for position, block_data in enumerate(llm_blocks):
        rb = ReportBlock(
            report_id=report.id,
            block_type=block_data.get("block_type", f"block_{position}"),
            heading=block_data.get("heading"),
            position=position,
            body_markdown=block_data.get("body_markdown", ""),
            structured=_coerce_structured(block_data.get("structured")),
            evidence=_coerce_evidence(block_data.get("evidence")),
        )
        db.add(rb)
        inserted_blocks.append(rb)
    await db.flush()

    # Use the local list to avoid an async lazy-load on report.blocks.
    block_outs = [
        ReportBlockOut(
            id=b.id,
            block_type=b.block_type,
            heading=b.heading,
            position=b.position,
            body_markdown=b.body_markdown,
            structured=b.structured,
            evidence=b.evidence,
        )
        for b in sorted(inserted_blocks, key=lambda b: b.position)
    ]

    log.info(
        "report.complete",
        extra={
            "kind": kind,
            "report_id": report.id,
            "blocks_persisted": len(block_outs),
            "duration_seconds": round(_time.monotonic() - started, 2),
            "model_used": report.model_used,
        },
    )

    return ReportResponse(
        report_id=report.id,
        kind=report.kind,
        title=report.title,
        summary=report.summary or "",
        gauges=GaugeSet(**gauges_data) if gauges_data else None,
        blocks=block_outs,
        model_used=report.model_used,
        created_at=report.created_at,
    )


async def run_full_mirror(*, db: AsyncSession, request: ReportRequest) -> ReportResponse:
    system_prompt = (
        "You are AI Mirror, a privacy-first self-reflection engine. You analyse "
        "the user's own AI conversation history and produce evidence-based "
        "insights about their thinking patterns, strengths, weaknesses, psychology, "
        "neurodivergence signals, and aptitudes. Be specific, kind, and grounded "
        "strictly in the provided corpus. Output JSON only."
    )
    return await _generate_report(
        db, "full_mirror", "Full Mirror Analysis", FULL_MIRROR_BLOCKS, request, system_prompt,
        extract_kg=True,
    )


async def run_advanced_abstract(*, db: AsyncSession, request: ReportRequest) -> ReportResponse:
    system_prompt = (
        "You are AI Mirror operating in Advanced Abstract mode. Produce a "
        "high-level synthesis: meta-patterns, conceptual lattice, philosophical "
        "signature, inner-dialogue motifs, and symbolic compression. Stay grounded "
        "in the corpus. Output JSON only."
    )
    return await _generate_report(
        db, "advanced_abstract", "Advanced Abstract Analysis", ABSTRACT_BLOCKS, request, system_prompt
    )


async def run_focus_lens(*, db: AsyncSession, request: FocusLensRequest) -> FocusLensResponse:
    """Selective, narrow analysis driven by a natural-language query."""
    stmt = (
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .order_by(Message.message_at.desc().nullslast(), Message.id.desc())
        .limit(200)
    )
    if request.date_from:
        stmt = stmt.where(Message.message_at >= request.date_from)
    if request.date_to:
        stmt = stmt.where(Message.message_at <= request.date_to)
    rows = (await db.execute(stmt)).scalars().all()
    corpus = "\n\n---\n\n".join(f"[{m.role}] {m.content[:1200]}" for m in rows)

    title = f"Focus Lens — {request.query[:80]}"
    if llm_available() and corpus.strip():
        try:
            payload = await chat_json(
                system=(
                    "You are AI Mirror's Focus Lens. Answer the user's targeted "
                    "question using only the supplied corpus. Provide a clear "
                    "Markdown answer with citations to specific excerpts. "
                    "Output JSON only with: summary, blocks[{block_type, heading, "
                    "body_markdown, structured, evidence}]."
                ),
                user=f"QUESTION: {request.query}\n\nCORPUS:\n{corpus[:60000]}",
                temperature=0.2,
                max_tokens=3000,
            )
            summary = payload.get("summary", "")
            blocks_data = payload.get("blocks") or []
        except Exception as exc:  # noqa: BLE001
            log.warning("focus_lens.llm_failed", extra={"error": str(exc)})
            summary = "LLM call failed — placeholder content rendered."
            blocks_data = []
    else:
        summary = "Configure an LLM provider to enable Focus Lens output."
        blocks_data = [
            {
                "block_type": "answer",
                "heading": "Answer",
                "body_markdown": (
                    f"## {request.query}\n\n_No LLM configured. Set "
                    "`LLM_PROVIDER` + an API key to enable analysis._"
                ),
                "structured": None,
                "evidence": [],
            }
        ]

    report = Report(
        kind="focus_lens",
        title=title,
        query=request.query,
        summary=summary,
        gauges=None,
        model_used=f"{settings.llm_provider}:{settings.llm_model}" if llm_available() else None,
    )
    db.add(report)
    await db.flush()

    inserted_blocks: list[ReportBlock] = []
    for position, block_data in enumerate(blocks_data):
        rb = ReportBlock(
            report_id=report.id,
            block_type=block_data.get("block_type", f"block_{position}"),
            heading=block_data.get("heading"),
            position=position,
            body_markdown=block_data.get("body_markdown", ""),
            structured=_coerce_structured(block_data.get("structured")),
            evidence=_coerce_evidence(block_data.get("evidence")),
        )
        db.add(rb)
        inserted_blocks.append(rb)
    await db.flush()

    block_outs = [
        ReportBlockOut(
            id=b.id,
            block_type=b.block_type,
            heading=b.heading,
            position=b.position,
            body_markdown=b.body_markdown,
            structured=b.structured,
            evidence=b.evidence,
        )
        for b in sorted(inserted_blocks, key=lambda b: b.position)
    ]

    return FocusLensResponse(
        report_id=report.id,
        title=report.title,
        summary=report.summary or "",
        blocks=block_outs,
        created_at=report.created_at,
    )


async def run_deep_dive(
    db: AsyncSession,
    request: DeepDiveRequest,
) -> DeepDiveResponse:
    """Run a deep-dive analysis on a specific block_type from Full Mirror reports."""
    import time as _time
    from fastapi import HTTPException

    started = _time.monotonic()

    log.info(
        "deep_dive.start",
        extra={
            "block_type_key": request.block_type,
            "has_focus_question": bool(request.focus_question),
            "sources_filter": bool(request.sources),
        },
    )

    # Step 1: Find most recent ReportBlock matching block_type from any Full Mirror report
    seed_block_result = await db.execute(
        select(ReportBlock)
        .join(Report, ReportBlock.report_id == Report.id)
        .where(
            ReportBlock.block_type == request.block_type,
            Report.kind == "full_mirror",
        )
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    seed_block = seed_block_result.scalar_one_or_none()
    if seed_block is None:
        raise HTTPException(
            status_code=404,
            detail="Run a Full Mirror analysis first to seed insights.",
        )
    source_report_id: int = seed_block.report_id

    # Step 2: Build corpus — same 400-message window; filter by source if requested
    corpus_stmt = (
        select(Message)
        .order_by(Message.message_at.desc().nullslast(), Message.id.desc())
        .limit(400)
    )
    if request.sources:
        corpus_stmt = (
            corpus_stmt
            .join(Conversation, Conversation.id == Message.conversation_id)
            .join(Source, Source.id == Conversation.source_id)
            .where(Source.slug.in_(request.sources))
        )
    corpus_rows = (await db.execute(corpus_stmt)).scalars().all()
    corpus = "\n\n---\n\n".join(f"[{m.role}] {m.content[:1200]}" for m in corpus_rows)

    # Step 3: LLM call
    focus_clause = (
        f"\n\nUser lens: {request.focus_question}" if request.focus_question else ""
    )
    seed_context = f"\n\nPrevious analysis of this theme:\n{seed_block.body_markdown[:3000]}"

    if llm_available() and corpus.strip():
        payload = await chat_json(
            system=(
                "You are AI Mirror's Deep Dive engine. Your task is to produce a rich, "
                "multi-paragraph analysis (1500–4000 characters) of a specific insight "
                "theme from the user's AI conversation history. Be specific, evidence-based, "
                "and grounded strictly in the provided corpus and previous analysis. "
                "Output JSON only with keys: heading (string), body_markdown (string, "
                "rich multi-paragraph Markdown, 1500–4000 chars), "
                "evidence (array of {snippet, source_slug, message_at} objects)."
            ),
            user=(
                f"THEME: {request.block_type}"
                + focus_clause
                + seed_context
                + f"\n\nCORPUS:\n{corpus[:60000]}"
            ),
            temperature=0.3,
            max_tokens=4096,
        )
        log.info(
            "deep_dive.llm_responded",
            extra={
                "block_type": request.block_type,
                "heading_chars": len(str(payload.get("heading", ""))),
                "body_chars": len(str(payload.get("body_markdown", ""))),
            },
        )
        heading = str(payload.get("heading") or request.block_type).strip()
        body_markdown = str(payload.get("body_markdown") or "").strip()
        raw_evidence = _coerce_evidence(payload.get("evidence")) or []
    else:
        heading = request.block_type.replace("_", " ").title()
        body_markdown = (
            f"## {heading}\n\n_Configure an LLM provider to enable Deep Dive analysis._"
        )
        raw_evidence = []

    # Coerce evidence items to Evidence schema
    evidence_out: list[Evidence] = []
    for ev in raw_evidence:
        if not isinstance(ev, dict):
            continue
        snippet = ev.get("snippet")
        if not isinstance(snippet, str) or not snippet.strip():
            continue
        source_slug = ev.get("source_slug")
        message_at_raw = ev.get("message_at")
        message_at: datetime | None = None
        if isinstance(message_at_raw, str):
            try:
                message_at = datetime.fromisoformat(message_at_raw)
            except ValueError:
                pass
        evidence_out.append(
            Evidence(
                snippet=snippet.strip(),
                source_slug=source_slug if isinstance(source_slug, str) else None,
                message_at=message_at,
            )
        )

    # Step 4: Persist as a new deep_dive Report + ReportBlock
    report_title = f"Deep Dive — {heading}"
    deep_dive_report = Report(
        kind="deep_dive",
        title=report_title[:512],
        query=request.focus_question,
        summary=body_markdown[:500] if body_markdown else None,
        gauges=None,
        model_used=f"{settings.llm_provider}:{settings.llm_model}" if llm_available() else None,
    )
    db.add(deep_dive_report)
    await db.flush()

    rb = ReportBlock(
        report_id=deep_dive_report.id,
        block_type=request.block_type,
        heading=heading,
        position=0,
        body_markdown=body_markdown,
        structured=None,
        evidence=[
            {
                "snippet": e.snippet,
                "source_slug": e.source_slug,
                "message_at": e.message_at.isoformat() if e.message_at else None,
            }
            for e in evidence_out
        ] or None,
    )
    db.add(rb)
    await db.flush()

    duration = round(_time.monotonic() - started, 2)
    log.info(
        "deep_dive.complete",
        extra={
            "block_type": request.block_type,
            "report_id": deep_dive_report.id,
            "duration_seconds": duration,
        },
    )

    return DeepDiveResponse(
        block_type=request.block_type,
        heading=heading,
        body_markdown=body_markdown,
        evidence=evidence_out,
        source_report_id=source_report_id,
        model_used=deep_dive_report.model_used,
        duration_seconds=duration,
        created_at=deep_dive_report.created_at,
    )
