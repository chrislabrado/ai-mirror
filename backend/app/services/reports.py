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
from app.schemas.reports import MetaAnalysisRequest, ReportRequest, ReportResponse
from app.services.analysis_v2 import (
    CLAIMS_SCHEMA_HINT,
    build_corpus,
    build_critique_block,
    build_run_digests,
    calibrate_gauges,
    dropped_thread_candidates,
    run_critique,
    verify_claims,
)
from app.services.llm import LLMUnavailable, chat_json, llm_available, resolve_model
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
    ("unrealized_opportunities", "Unrealized Opportunities"),
    ("actionable_insights", "Actionable Insights"),
]

META_ANALYSIS_BLOCKS: list[tuple[str, str]] = [
    ("stability_map", "Stability Map"),
    ("drift", "What Actually Changed"),
    ("narrative_variance", "Model Noise vs Real Change"),
    ("open_questions", "Open Questions"),
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
            "structured": {"placeholder": True},
            "evidence": [],
        }
        for slug, heading in blocks
    ]


def _model_used(fable: bool | None) -> str | None:
    """Human-readable model attribution, fable-aware."""
    if not llm_available():
        return None
    fable_on = settings.fable_mode if fable is None else fable
    if fable_on:
        return (
            f"{settings.llm_provider}:{resolve_model('hard', True)}"
            f"+{resolve_model('scaffold', True)} (fable)"
        )
    return f"{settings.llm_provider}:{settings.llm_model}"


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
    fable = request.fable
    if llm_available():
        corpus = await build_corpus(
            db, date_from=request.date_from, date_to=request.date_to, fable=fable
        )
    else:
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

            opportunity_instruction = ""
            if any(slug == "unrealized_opportunities" for slug, _ in blocks):
                candidates = await dropped_thread_candidates(db)
                if candidates:
                    cand_lines = "\n".join(
                        f"  [conv:{c['conversation_id']}] ({c['at'] or '—'}) "
                        f"{c['title'] or '—'}: last user msg: {c['last_user_message']}"
                        for c in candidates
                    )
                    opportunity_instruction = (
                        "\n\nFor the unrealized_opportunities block, consider (a) these "
                        "detected dropped threads — conversations that ended on an open "
                        "user question:\n" + cand_lines + "\n(b) aptitudes demonstrated "
                        "but never exploited, (c) cross-domain transfer — patterns "
                        "mastered in one domain and absent in an adjacent one, (d) "
                        "questions the user never asked but their trajectory suggests "
                        "they should."
                    )

            payload = await chat_json(
                system=system_prompt,
                user=(
                    "Analyse the following corpus (epoch tables, conversation index, "
                    "id-labelled excerpts) and produce a structured JSON object with:\n"
                    "- summary: 4-5 concise bullet observations (one string per bullet, "
                    "joined by newlines)\n"
                    "- gauges: {thought_clarity, self_reflection_depth, aptitude_balance} "
                    "each a float between 0 and 1\n"
                    "- blocks: array of {block_type, heading, body_markdown, structured, "
                    "evidence}. Each block's `structured` MUST contain a `claims` array "
                    f"matching {CLAIMS_SCHEMA_HINT}. RULES: cite only message ids that "
                    "appear as [msg:<id>] in the corpus; quotes must be verbatim "
                    "substrings of that message (they are machine-verified — invented "
                    "quotes are discarded and the claim is demoted); every non-obvious "
                    "claim needs at least one evidence entry; state counter-evidence "
                    "honestly (null only when none exists); confidence reflects the "
                    "evidence, not politeness. Register: candid, warm-neutral, "
                    "evidence-first — no flattery, no harshness.\n"
                    "For growth_arc, reason from the EPOCH TABLE trends, not vibes."
                    + opportunity_instruction
                    + f"\n\nExpected block_types in order: {[b[0] for b in blocks]}\n\n"
                    f"CORPUS:\n{corpus}"
                ),
                temperature=0.3,
                max_tokens=16384,
                tier="hard",
                fable=fable,
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
            summary = payload.get("summary", "")
            if isinstance(summary, list):
                summary = "\n".join(str(s) for s in summary)
            summary = str(summary).strip()
            gauges_data = payload.get("gauges") or None
            llm_blocks = [b for b in (payload.get("blocks") or []) if isinstance(b, dict)]
            if not llm_blocks:
                llm_blocks = _placeholder_blocks(blocks)

            # v2 grounding gate — verify every cited quote against the real rows.
            grounding = await verify_claims(db, llm_blocks)

            # v2 adversarial critique — the draft must survive its own refutation.
            try:
                critique = await run_critique(llm_blocks, corpus[:30_000], fable=fable)
            except Exception as crit_exc:  # noqa: BLE001
                log.warning("critique.failed", extra={"error": str(crit_exc)})
                critique = {
                    "overall": f"Critique pass failed ({crit_exc}); verdicts unavailable.",
                    "verdicts": [],
                }
            llm_blocks.append(build_critique_block(critique, grounding))
            gauges_data = calibrate_gauges(gauges_data, grounding, critique)

            # Knowledge-graph extraction (Full Mirror only) — separate scaffold-tier
            # call so the hard-tier synthesis stays focused on judgment.
            if extract_kg:
                try:
                    kg_payload = await chat_json(
                        system=(
                            "You extract a knowledge graph from a personal "
                            "AI-conversation corpus. Output JSON only."
                        ),
                        user=(
                            "Extract a knowledge graph with:\n"
                            "- entities: 40-80 entries {label, kind, salience, description}; "
                            "kind one of concept | person | tool | project | belief | trait "
                            "| source | topic; salience in [0,1]; description grounded in "
                            "the corpus.\n"
                            "- relationships: at least 2 per entity on average, {subject, "
                            "predicate, object, weight}; subject/object MUST exactly match "
                            "entity labels; predicate snake_case (uses, is_building, "
                            "depends_on, is_motivated_by, ...); weight in [0,1]; every "
                            "entity appears in at least one relationship. Breadth over "
                            "depth.\n\n"
                            f"CORPUS:\n{corpus[:60000]}"
                        ),
                        temperature=0.2,
                        max_tokens=16384,
                        tier="scaffold",
                        fable=fable,
                    )
                    ent_count, rel_count = await _persist_knowledge_graph(db, kg_payload)
                    log.info(
                        "kg.persisted",
                        extra={"entity_count": ent_count, "relationship_count": rel_count},
                    )
                except Exception as kg_exc:  # noqa: BLE001
                    log.warning("kg.extraction_failed", extra={"error": str(kg_exc)})

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
        model_used=_model_used(fable),
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
        "neurodivergence signals, and aptitudes. Be specific and grounded strictly "
        "in the provided corpus. Register contract: candid, warm-neutral, "
        "evidence-first — flattery and harshness are both failures. Weaknesses get "
        "the same evidentiary rigor as strengths. Output JSON only."
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
    corpus = "\n\n---\n\n".join(
        f"[msg:{m.id}] [{m.role}] {m.content[:1200]}" for m in rows
    )

    fable = request.fable
    title = f"Focus Lens — {request.query[:80]}"
    if llm_available() and corpus.strip():
        try:
            payload = await chat_json(
                system=(
                    "You are AI Mirror's Focus Lens. Answer the user's targeted "
                    "question using only the supplied corpus. Provide a clear "
                    "Markdown answer. Output JSON only with: summary, "
                    "blocks[{block_type, heading, body_markdown, structured, "
                    "evidence}]. Each block's `structured` MUST contain a `claims` "
                    f"array matching {CLAIMS_SCHEMA_HINT}; cite only [msg:<id>] ids "
                    "you saw; quotes must be verbatim (machine-verified). Candid, "
                    "warm-neutral, evidence-first."
                ),
                user=f"QUESTION: {request.query}\n\nCORPUS:\n{corpus[:60000]}",
                temperature=0.2,
                max_tokens=4096,
                tier="hard",
                fable=fable,
            )
            summary = payload.get("summary", "")
            if isinstance(summary, list):
                summary = "\n".join(str(s) for s in summary)
            blocks_data = [b for b in (payload.get("blocks") or []) if isinstance(b, dict)]
            await verify_claims(db, blocks_data)
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
        model_used=_model_used(fable),
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
        model_used=_model_used(None),
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


async def run_meta_analysis(*, db: AsyncSession, request: MetaAnalysisRequest) -> ReportResponse:
    """Compare the last N full-mirror runs: stability, drift, model noise.

    Evidence here cites *reports*, not messages, so the grounding gate is the
    digest itself — every input the model saw is stored in the report's
    structured payload for audit.
    """
    from fastapi import HTTPException

    digests = await build_run_digests(db, compare_last=request.compare_last)
    if len(digests) < 2:
        raise HTTPException(
            status_code=400,
            detail="Meta-analysis needs at least two Full Mirror runs to compare.",
        )

    fable = request.fable
    title = f"Meta-Analysis of {len(digests)} Mirror Runs — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    import json as _json

    digest_text = _json.dumps(digests, ensure_ascii=False)[:80_000]
    try:
        payload = await chat_json(
            system=(
                "You are AI Mirror's meta-analyst. You receive digests of several "
                "prior Full Mirror self-reflection reports about the same person "
                "(newest first). Separate three things rigorously: (1) traits that "
                "are STABLE across runs (test-retest reliability), (2) genuine "
                "CHANGE in the person over time, (3) NARRATIVE VARIANCE — the "
                "model describing the same facts differently run-to-run, which is "
                "noise, not change. Candid, warm-neutral, evidence-first; cite "
                "report ids like [report:12]. Output JSON only."
            ),
            user=(
                "Produce: summary (3-5 bullets joined by newlines) and blocks "
                "[{block_type, heading, body_markdown, structured, evidence}] with "
                f"block_types in order: {[b[0] for b in META_ANALYSIS_BLOCKS]}. "
                "Each block's structured.claims follows "
                '{claims: [{claim, confidence: "high"|"medium"|"low", '
                "evidence: [{report_id: int, note: str}], counter_evidence}]}.\n\n"
                f"RUN DIGESTS (newest first):\n{digest_text}"
            ),
            temperature=0.2,
            max_tokens=8192,
            tier="hard",
            fable=fable,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("meta_analysis.llm_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail=f"Meta-analysis LLM call failed: {exc}")

    summary = payload.get("summary", "")
    if isinstance(summary, list):
        summary = "\n".join(str(s) for s in summary)
    blocks_data = [b for b in (payload.get("blocks") or []) if isinstance(b, dict)]

    report = Report(
        kind="meta_analysis",
        title=title,
        query=f"compare_last={request.compare_last}",
        summary=str(summary).strip(),
        gauges=None,
        model_used=_model_used(fable),
    )
    db.add(report)
    await db.flush()

    def _report_evidence(value: object) -> list[dict[str, object]] | None:
        # Meta-analysis evidence cites reports ({report_id, note}); normalise
        # into the legacy Evidence shape (snippet required).
        items = _coerce_evidence(value) or []
        out: list[dict[str, object]] = []
        for ev in items:
            if "snippet" not in ev:
                rid = ev.get("report_id")
                note = ev.get("note") or ""
                ev = {"snippet": f"[report:{rid}] {note}".strip()}
            out.append(ev)
        return out or None

    inserted: list[ReportBlock] = []
    for position, block_data in enumerate(blocks_data):
        structured = _coerce_structured(block_data.get("structured")) or {}
        if position == 0:
            # Audit trail: persist exactly which runs were compared.
            structured["compared_report_ids"] = [d["report_id"] for d in digests]
        rb = ReportBlock(
            report_id=report.id,
            block_type=block_data.get("block_type", f"block_{position}"),
            heading=block_data.get("heading"),
            position=position,
            body_markdown=block_data.get("body_markdown", ""),
            structured=structured,
            evidence=_report_evidence(block_data.get("evidence")),
        )
        db.add(rb)
        inserted.append(rb)
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
        for b in sorted(inserted, key=lambda b: b.position)
    ]

    log.info(
        "meta_analysis.complete",
        extra={"report_id": report.id, "runs_compared": len(digests), "blocks": len(block_outs)},
    )
    return ReportResponse(
        report_id=report.id,
        kind=report.kind,
        title=report.title,
        summary=report.summary or "",
        gauges=None,
        blocks=block_outs,
        model_used=report.model_used,
        created_at=report.created_at,
    )
