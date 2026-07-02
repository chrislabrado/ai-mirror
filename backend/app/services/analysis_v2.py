"""Analysis Engine v2 — grounding, corpus assembly, critique, meta-analysis.

The v2 contract (docs/DESIGN-V2_2026-07-02.md):

- Every report block carries ``structured.claims[]``:
  ``{claim, confidence, evidence: [{message_id, quote}], counter_evidence}``.
- Evidence is *verified by the backend* against the actual message rows.
  Quotes the model invented don't survive; claims with no surviving
  evidence are demoted and tagged ``ungrounded``.
- An adversarial critique pass (hard tier) tries to refute the draft —
  sycophancy, overreach, unsupported claims — and its verdicts are stored
  with the report.
- The corpus is hierarchical: cached per-conversation summaries + epoch
  stats/profiles + id-labelled raw excerpts, instead of "last 400 messages".
  Excerpts are labelled ``[msg:<id>]`` so the model can only cite ids it
  actually saw.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Source
from app.models.message import Message
from app.models.report import Report, ReportBlock
from app.services.llm import chat_json
from app.utils.logger import get_logger

log = get_logger(__name__)

_WS = re.compile(r"\s+")

CLAIMS_SCHEMA_HINT = (
    '{claims: [{claim: str, confidence: "high"|"medium"|"low", '
    "evidence: [{message_id: int (an id you saw as [msg:<id>]), quote: str "
    "(verbatim text copied from that message)}], counter_evidence: str|null}]}"
)


def _norm(text: str) -> str:
    return _WS.sub(" ", text.casefold()).strip()


def _word_overlap(quote: str, content: str) -> float:
    """Fraction of significant quote words present in the message content."""
    q_words = [w for w in _norm(quote).split() if len(w) >= 4]
    if not q_words:
        return 0.0
    c_norm = _norm(content)
    hits = sum(1 for w in q_words if w in c_norm)
    return hits / len(q_words)


# ---------------------------------------------------------------------------
# Conversation summaries (map phase, scaffold tier)
# ---------------------------------------------------------------------------

_SUMMARY_BATCH = 12
_SUMMARY_MAX_PER_RUN = 60


async def ensure_conversation_summaries(
    db: AsyncSession, *, fable: bool | None = None
) -> tuple[int, int]:
    """Summarise conversations lacking a cached summary.

    Returns (summarised_now, still_unsummarised). Bounded per run so a first
    run over a huge history doesn't burn the world; repeated runs converge.
    """
    pending = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.summary.is_(None))
                .order_by(Conversation.started_at.desc().nullslast())
                .limit(_SUMMARY_MAX_PER_RUN + 1)
            )
        )
        .scalars()
        .all()
    )
    overflow = len(pending) > _SUMMARY_MAX_PER_RUN
    pending = pending[:_SUMMARY_MAX_PER_RUN]
    if not pending:
        return 0, 0

    done = 0
    for i in range(0, len(pending), _SUMMARY_BATCH):
        batch = pending[i : i + _SUMMARY_BATCH]
        entries: list[str] = []
        for conv in batch:
            msgs = (
                (
                    await db.execute(
                        select(Message)
                        .where(Message.conversation_id == conv.id)
                        .order_by(Message.sequence)
                        .limit(6)
                    )
                )
                .scalars()
                .all()
            )
            excerpt = " | ".join(f"[{m.role}] {m.content[:280]}" for m in msgs)
            entries.append(
                f"conversation_id={conv.id} title={conv.title or '—'} "
                f"date={conv.started_at.date() if conv.started_at else '—'} "
                f"messages={conv.message_count}\nEXCERPT: {excerpt[:1800]}"
            )
        try:
            payload = await chat_json(
                system=(
                    "You summarise AI-chat conversations for a self-reflection "
                    "index. For each conversation return a factual, non-flattering "
                    "summary of what the USER was doing/asking (max 40 words) and "
                    "up to 3 theme tags. No speculation beyond the excerpt."
                ),
                user="\n\n---\n\n".join(entries),
                schema_hint='{summaries: [{conversation_id: int, summary: str, themes: [str]}]}',
                temperature=0.1,
                max_tokens=2048,
                tier="scaffold",
                fable=fable,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("summaries.batch_failed", extra={"error": str(exc)})
            continue
        by_id = {c.id: c for c in batch}
        for item in payload.get("summaries") or []:
            if not isinstance(item, dict):
                continue
            conv = by_id.get(item.get("conversation_id"))
            summary = item.get("summary")
            if conv is None or not isinstance(summary, str) or not summary.strip():
                continue
            themes = item.get("themes")
            tag = ""
            if isinstance(themes, list) and themes:
                tag = " [" + ", ".join(str(t) for t in themes[:3]) + "]"
            conv.summary = (summary.strip() + tag)[:600]
            done += 1
    await db.flush()

    remaining = 0
    if overflow:
        remaining = (
            await db.execute(
                select(func.count()).select_from(Conversation).where(Conversation.summary.is_(None))
            )
        ).scalar_one()
    log.info("summaries.ensured", extra={"summarised": done, "remaining": remaining})
    return done, remaining


# ---------------------------------------------------------------------------
# Hierarchical corpus
# ---------------------------------------------------------------------------

_CORPUS_CHAR_BUDGET = 150_000


async def build_corpus(
    db: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    fable: bool | None = None,
) -> str:
    """Assemble the hierarchical corpus: epoch tables + summaries + labelled excerpts."""
    await ensure_conversation_summaries(db, fable=fable)

    sections: list[str] = []

    # 1. Epoch stats table (deterministic; computed by the temporal engine)
    try:
        from app.services.temporal import compute_epoch_stats

        epoch_rows = await compute_epoch_stats(db)
        if epoch_rows:
            lines = ["EPOCH TABLE (deterministic monthly aggregates):"]
            for row in epoch_rows:
                stats = row.get("stats") or row
                lines.append(
                    f"  {row.get('epoch')}: msgs={stats.get('messages')} "
                    f"convs={stats.get('conversations')} "
                    f"avg_user_chars={stats.get('avg_user_msg_chars')} "
                    f"question_ratio={stats.get('question_ratio')} "
                    f"active_days={stats.get('active_days')}"
                )
            sections.append("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        log.warning("corpus.epoch_stats_failed", extra={"error": str(exc)})

    # 2. Conversation summary index (most recent 250)
    convs = (
        (
            await db.execute(
                select(Conversation, Source.slug)
                .join(Source, Source.id == Conversation.source_id)
                .where(Conversation.summary.is_not(None))
                .order_by(Conversation.started_at.desc().nullslast())
                .limit(250)
            )
        )
        .all()
    )
    if convs:
        lines = ["CONVERSATION INDEX (cached summaries, newest first):"]
        for conv, slug in convs:
            date = conv.started_at.date().isoformat() if conv.started_at else "—"
            lines.append(f"  [conv:{conv.id}] {date} ({slug}) {conv.summary}")
        sections.append("\n".join(lines))

    # 3. Raw excerpts, id-labelled — recent window
    stmt = (
        select(Message)
        .order_by(Message.message_at.desc().nullslast(), Message.id.desc())
        .limit(120)
    )
    if date_from:
        stmt = stmt.where(Message.message_at >= date_from)
    if date_to:
        stmt = stmt.where(Message.message_at <= date_to)
    recent = (await db.execute(stmt)).scalars().all()
    if recent:
        lines = ["RECENT MESSAGES (verbatim, cite by [msg:<id>]):"]
        for m in reversed(recent):
            lines.append(f"  [msg:{m.id}] [{m.role}] {m.content[:500]}")
        sections.append("\n".join(lines))

    # 4. Historical spread — up to 6 user messages per month, id-labelled
    monthly = (
        await db.execute(
            select(
                func.strftime("%Y-%m", Message.message_at).label("epoch"),
                Message.id,
            )
            .where(Message.role == "user", Message.message_at.is_not(None))
            .order_by(Message.message_at)
        )
    ).all()
    by_epoch: dict[str, list[int]] = {}
    for epoch, mid in monthly:
        by_epoch.setdefault(epoch, []).append(mid)
    spread_ids: list[int] = []
    recent_ids = {m.id for m in recent}
    for epoch, ids in by_epoch.items():
        step = max(1, len(ids) // 6)
        spread_ids.extend(i for i in ids[::step][:6] if i not in recent_ids)
    if spread_ids:
        rows = (
            (await db.execute(select(Message).where(Message.id.in_(spread_ids)).order_by(Message.message_at)))
            .scalars()
            .all()
        )
        lines = ["HISTORICAL USER MESSAGES (spread across months, cite by [msg:<id>]):"]
        for m in rows:
            date = m.message_at.date().isoformat() if m.message_at else "—"
            lines.append(f"  [msg:{m.id}] {date} {m.content[:350]}")
        sections.append("\n".join(lines))

    corpus = "\n\n=====\n\n".join(sections)
    if len(corpus) > _CORPUS_CHAR_BUDGET:
        corpus = corpus[:_CORPUS_CHAR_BUDGET]
    log.info(
        "corpus.built",
        extra={
            "chars": len(corpus),
            "summaries": len(convs),
            "recent_msgs": len(recent),
            "spread_msgs": len(spread_ids),
        },
    )
    return corpus


# ---------------------------------------------------------------------------
# Opportunity candidates (deterministic seeds for the unrealized-angles block)
# ---------------------------------------------------------------------------


async def dropped_thread_candidates(db: AsyncSession, limit: int = 10) -> list[dict[str, Any]]:
    """Conversations whose final message is from the user — likely open loops."""
    last_seq = (
        select(
            Message.conversation_id,
            func.max(Message.sequence).label("max_seq"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Conversation.id, Conversation.title, Message.content, Message.message_at)
            .join(last_seq, last_seq.c.conversation_id == Conversation.id)
            .join(
                Message,
                (Message.conversation_id == Conversation.id)
                & (Message.sequence == last_seq.c.max_seq),
            )
            .where(Message.role == "user")
            .order_by(Message.message_at.desc().nullslast())
            .limit(limit)
        )
    ).all()
    return [
        {
            "conversation_id": cid,
            "title": title,
            "last_user_message": content[:280],
            "at": at.isoformat() if at else None,
        }
        for cid, title, content, at in rows
    ]


# ---------------------------------------------------------------------------
# Evidence verification (deterministic — the anti-hallucination gate)
# ---------------------------------------------------------------------------


async def verify_claims(db: AsyncSession, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify every claim's evidence quotes against the real message rows.

    Mutates blocks in place: evidence entries gain ``verified``,
    ``conversation_id``, ``message_at``, ``source_slug``; claims with no
    verified evidence are demoted to low confidence and tagged
    ``ungrounded``. The legacy block-level ``evidence`` list is rebuilt
    from verified entries so the existing UI keeps working.

    Returns grounding stats.
    """
    cited_ids: set[int] = set()
    for block in blocks:
        for claim in ((block.get("structured") or {}).get("claims") or []):
            for ev in claim.get("evidence") or []:
                if isinstance(ev, dict) and isinstance(ev.get("message_id"), int):
                    cited_ids.add(ev["message_id"])

    msg_rows: dict[int, tuple[Message, str]] = {}
    if cited_ids:
        rows = (
            await db.execute(
                select(Message, Source.slug)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .join(Source, Source.id == Conversation.source_id)
                .where(Message.id.in_(cited_ids))
            )
        ).all()
        msg_rows = {m.id: (m, slug) for m, slug in rows}

    total_claims = 0
    grounded_claims = 0
    verified_evidence = 0
    total_evidence = 0

    for block in blocks:
        structured = block.get("structured")
        claims = (structured or {}).get("claims")
        if not isinstance(claims, list):
            continue
        block_verified_evidence: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            total_claims += 1
            claim_verified = False
            for ev in claim.get("evidence") or []:
                if not isinstance(ev, dict):
                    continue
                total_evidence += 1
                mid = ev.get("message_id")
                quote = ev.get("quote") or ev.get("snippet") or ""
                hit = msg_rows.get(mid) if isinstance(mid, int) else None
                ok = False
                if hit and isinstance(quote, str) and quote.strip():
                    msg, slug = hit
                    nq, nc = _norm(quote), _norm(msg.content)
                    ok = (nq in nc) or (_word_overlap(quote, msg.content) >= 0.8)
                    if ok:
                        ev.update(
                            verified=True,
                            conversation_id=msg.conversation_id,
                            message_at=msg.message_at.isoformat() if msg.message_at else None,
                            source_slug=slug,
                        )
                        verified_evidence += 1
                        block_verified_evidence.append(
                            {
                                "message_id": msg.id,
                                "conversation_id": msg.conversation_id,
                                "snippet": quote[:400],
                                "source_slug": slug,
                                "message_at": ev["message_at"],
                            }
                        )
                if not ok:
                    ev["verified"] = False
            if any(
                isinstance(ev, dict) and ev.get("verified") for ev in claim.get("evidence") or []
            ):
                claim_verified = True
                grounded_claims += 1
            else:
                claim["ungrounded"] = True
                claim["confidence"] = "low"
            claim.setdefault("annotations", [])
            _ = claim_verified
        # Rebuild legacy evidence from verified entries (dedup by message_id)
        seen: set[int] = set()
        legacy: list[dict[str, Any]] = []
        for ev in block_verified_evidence:
            if ev["message_id"] in seen:
                continue
            seen.add(ev["message_id"])
            legacy.append(ev)
        if legacy:
            block["evidence"] = legacy[:8]

    stats = {
        "total_claims": total_claims,
        "grounded_claims": grounded_claims,
        "grounding_ratio": round(grounded_claims / total_claims, 3) if total_claims else None,
        "verified_evidence": verified_evidence,
        "total_evidence": total_evidence,
    }
    log.info("evidence.verified", extra=dict(stats))
    return stats


# ---------------------------------------------------------------------------
# Adversarial critique (anti-sycophancy gate, hard tier)
# ---------------------------------------------------------------------------


async def run_critique(
    blocks: list[dict[str, Any]],
    corpus_sample: str,
    *,
    fable: bool | None = None,
) -> dict[str, Any]:
    """Hostile review of the draft report. Returns the critique payload and
    applies demotions/annotations to the blocks in place."""
    digest_lines: list[str] = []
    for block in blocks:
        digest_lines.append(f"## {block.get('heading') or block.get('block_type')}")
        digest_lines.append((block.get("body_markdown") or "")[:1500])
        for idx, claim in enumerate(((block.get("structured") or {}).get("claims") or [])):
            if isinstance(claim, dict):
                digest_lines.append(
                    f"  CLAIM[{block.get('block_type')}#{idx}] "
                    f"({claim.get('confidence')}"
                    f"{', UNGROUNDED' if claim.get('ungrounded') else ''}): "
                    f"{str(claim.get('claim'))[:300]}"
                )
    digest = "\n".join(digest_lines)[:40_000]

    payload = await chat_json(
        system=(
            "You are the adversarial reviewer of a self-reflection report about a "
            "person, generated from their AI conversation history. Your job is to "
            "REFUTE it. Hunt for: (1) sycophancy — flattery not earned by evidence; "
            "(2) overreach — claims stronger than the evidence supports; (3) "
            "unsupported psychological or clinical speculation; (4) tone drift — "
            "anything hostile, terse, or performatively harsh (the opposite "
            "overcorrection). The target register is candid, warm-neutral, "
            "evidence-first. Judge against the corpus sample. Be specific; cite "
            "the CLAIM[...] handles."
        ),
        user=f"DRAFT REPORT:\n{digest}\n\nCORPUS SAMPLE (ground truth):\n{corpus_sample[:30_000]}",
        schema_hint=(
            '{verdicts: [{target: str (the CLAIM[block#i] handle or block name), '
            'issue: "sycophancy"|"overreach"|"unsupported"|"tone", severity: '
            '"low"|"medium"|"high", note: str}], overall: str (2-4 candid '
            "sentences), sycophancy_score: float 0-1 (0 = fully earned, 1 = pure "
            "flattery), balance_score: float 0-1 (1 = calibrated, neither "
            "flattering nor harsh)}"
        ),
        temperature=0.2,
        max_tokens=4096,
        tier="hard",
        fable=fable,
    )

    verdicts = payload.get("verdicts") or []
    handle_re = re.compile(r"CLAIM\[(\w+)#(\d+)\]")
    demoted = 0
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        m = handle_re.search(str(verdict.get("target") or ""))
        if not m:
            continue
        btype, idx = m.group(1), int(m.group(2))
        for block in blocks:
            if block.get("block_type") != btype:
                continue
            claims = (block.get("structured") or {}).get("claims") or []
            if idx < len(claims) and isinstance(claims[idx], dict):
                claims[idx].setdefault("annotations", []).append(
                    {
                        "issue": verdict.get("issue"),
                        "severity": verdict.get("severity"),
                        "note": str(verdict.get("note"))[:400],
                    }
                )
                if verdict.get("severity") == "high" and claims[idx].get("confidence") != "low":
                    claims[idx]["confidence"] = "low"
                    demoted += 1
    log.info(
        "critique.done",
        extra={
            "verdicts": len(verdicts),
            "demoted": demoted,
            "sycophancy_score": payload.get("sycophancy_score"),
        },
    )
    return payload


def build_critique_block(critique: dict[str, Any], grounding: dict[str, Any]) -> dict[str, Any]:
    """Render the critique as a first-class report block."""
    verdicts = [v for v in (critique.get("verdicts") or []) if isinstance(v, dict)]
    lines = [
        "This report was adversarially reviewed before delivery. The reviewer's "
        "job was to refute it — flag flattery, overreach, and unsupported claims.",
        "",
        f"- **Sycophancy score:** {critique.get('sycophancy_score', '—')} (0 = fully earned, 1 = pure flattery)",
        f"- **Balance score:** {critique.get('balance_score', '—')} (1 = calibrated)",
        f"- **Grounding:** {grounding.get('grounded_claims', 0)}/{grounding.get('total_claims', 0)} "
        f"claims carry backend-verified evidence "
        f"(ratio {grounding.get('grounding_ratio')})",
        "",
    ]
    if critique.get("overall"):
        lines += ["**Reviewer's overall verdict:**", "", str(critique["overall"]), ""]
    if verdicts:
        lines.append("**Standing objections:**")
        lines.append("")
        for v in verdicts[:12]:
            lines.append(
                f"- `{v.get('target')}` — {v.get('issue')} ({v.get('severity')}): "
                f"{str(v.get('note'))[:300]}"
            )
    return {
        "block_type": "critique",
        "heading": "Adversarial Review",
        "body_markdown": "\n".join(lines),
        "structured": {"critique": critique, "grounding": grounding},
        "evidence": [],
    }


def calibrate_gauges(
    model_gauges: dict[str, Any] | None, grounding: dict[str, Any], critique: dict[str, Any]
) -> dict[str, Any] | None:
    """Blend the model's gauge suggestions with deterministic quality signals.

    60% model judgment, 40% measured: grounding ratio and the critique's
    balance score. Keeps the numbers honest without pretending the whole
    gauge is objective.
    """
    if not isinstance(model_gauges, dict):
        return None
    ratio = grounding.get("grounding_ratio")
    balance = critique.get("balance_score")
    measured = [v for v in (ratio, balance) if isinstance(v, (int, float))]
    measured_score = sum(measured) / len(measured) if measured else None
    out: dict[str, Any] = {}
    for key in ("thought_clarity", "self_reflection_depth", "aptitude_balance"):
        try:
            model_val = float(model_gauges.get(key))
        except (TypeError, ValueError):
            return model_gauges
        if measured_score is None:
            out[key] = round(min(1.0, max(0.0, model_val)), 3)
        else:
            out[key] = round(min(1.0, max(0.0, 0.6 * model_val + 0.4 * measured_score)), 3)
    return out


# ---------------------------------------------------------------------------
# Meta-analysis across mirror runs
# ---------------------------------------------------------------------------


async def build_run_digests(db: AsyncSession, compare_last: int = 5) -> list[dict[str, Any]]:
    """Compact per-run digests of previous full-mirror reports."""
    reports = (
        (
            await db.execute(
                select(Report)
                .where(Report.kind == "full_mirror")
                .order_by(Report.created_at.desc())
                .limit(compare_last)
            )
        )
        .scalars()
        .all()
    )
    digests: list[dict[str, Any]] = []
    for report in reports:
        blocks = (
            (
                await db.execute(
                    select(ReportBlock)
                    .where(ReportBlock.report_id == report.id)
                    .order_by(ReportBlock.position)
                )
            )
            .scalars()
            .all()
        )
        block_digests = []
        for b in blocks:
            if b.block_type == "critique":
                continue
            claims = ((b.structured or {}).get("claims") or [])[:4]
            claim_lines = [
                f"({c.get('confidence')}{', ungrounded' if c.get('ungrounded') else ''}) {str(c.get('claim'))[:200]}"
                for c in claims
                if isinstance(c, dict)
            ]
            block_digests.append(
                {
                    "block_type": b.block_type,
                    "claims": claim_lines,
                    "body_head": (b.body_markdown or "")[:300],
                }
            )
        digests.append(
            {
                "report_id": report.id,
                "created_at": report.created_at.isoformat(),
                "model_used": report.model_used,
                "summary": report.summary,
                "gauges": report.gauges,
                "blocks": block_digests,
            }
        )
    return digests
