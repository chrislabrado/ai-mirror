"""Temporal engine — epoch tables + synthetic extrapolation.

Three layers, cheapest first:

1. :func:`compute_epoch_stats` — deterministic per-month aggregates, pure SQL,
   no LLM. Upserted into ``epoch_profiles.stats``.
2. :func:`profile_epochs` — scaffold-tier LLM characterisation of each epoch
   (themes, sophistication, delegation, valence, shifts), cached in
   ``epoch_profiles.profile``; only unprofiled epochs are sent unless forced.
3. :func:`synthesize_trajectories` — hard-tier synthesis over the observed
   epoch tables: per-metric series extrapolated exactly 2 epochs forward,
   every synthetic point explicitly ``kind="extrapolated"`` with a confidence
   band, plus stated assumptions and a global abstraction.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Source
from app.models.epoch import EpochProfile, Trajectory
from app.models.message import Message
from app.services.llm import chat_json, resolve_model
from app.utils.logger import get_logger

log = get_logger(__name__)

_EPOCH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_PROFILE_SAMPLE_MAX = 40
_PROFILE_MSG_CHARS = 300
_PROFILE_CONCURRENCY = 3
_EXTRAPOLATED_POINTS = 2

# Canonical metric order for trajectory synthesis. The first three come from
# deterministic stats; the last three from cached LLM epoch profiles.
_STAT_METRICS = ("messages", "question_ratio", "avg_user_msg_chars")
_PROFILE_METRICS = ("sophistication", "delegation", "valence")

ABSTRACTION_METRIC = "__abstraction__"


def _epoch_label(epoch_start: date) -> str:
    return f"{epoch_start.year:04d}-{epoch_start.month:02d}"


def _epoch_start_from_label(label: str) -> date:
    year, month = label.split("-")
    return date(int(year), int(month), 1)


def _next_epoch_label(label: str, steps: int = 1) -> str:
    d = _epoch_start_from_label(label)
    total = d.year * 12 + (d.month - 1) + steps
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _clamp(value: object, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# 1. Deterministic epoch stats (pure SQL)
# ---------------------------------------------------------------------------


async def compute_epoch_stats(db: AsyncSession) -> list[dict]:
    """Compute per-month aggregates from messages and upsert EpochProfile rows.

    All-sources scope (``source_slug=None``, ``epoch_kind="month"``). Existing
    LLM ``profile`` payloads are preserved; only ``stats`` is refreshed.
    Returns the ordered list of stats dicts (each includes its epoch label).
    """
    month = func.strftime("%Y-%m", Message.message_at)
    is_user = Message.role == "user"

    agg_rows = (
        await db.execute(
            select(
                month.label("epoch"),
                func.count(func.distinct(Message.conversation_id)).label("conversations"),
                func.count(Message.id).label("messages"),
                func.sum(case((is_user, 1), else_=0)).label("user_messages"),
                func.sum(case((Message.role == "assistant", 1), else_=0)).label(
                    "assistant_messages"
                ),
                func.avg(case((is_user, func.length(Message.content)))).label(
                    "avg_user_msg_chars"
                ),
                func.sum(
                    case(((is_user & Message.content.contains("?")), 1), else_=0)
                ).label("user_question_messages"),
                func.count(func.distinct(func.date(Message.message_at))).label("active_days"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(Source, Conversation.source_id == Source.id)
            .where(Message.message_at.is_not(None))
            .group_by(month)
            .order_by(month)
        )
    ).all()

    src_rows = (
        await db.execute(
            select(
                month.label("epoch"),
                Source.slug,
                func.count(Message.id).label("messages"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(Source, Conversation.source_id == Source.id)
            .where(Message.message_at.is_not(None))
            .group_by(month, Source.slug)
        )
    ).all()

    by_source: dict[str, dict[str, int]] = {}
    for row in src_rows:
        by_source.setdefault(row.epoch, {})[row.slug] = int(row.messages)

    existing = {
        row.epoch_start: row
        for row in (
            await db.execute(
                select(EpochProfile).where(
                    EpochProfile.epoch_kind == "month",
                    EpochProfile.source_slug.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    stats_out: list[dict] = []
    for row in agg_rows:
        user_messages = int(row.user_messages or 0)
        stats = {
            "epoch": row.epoch,
            "conversations": int(row.conversations),
            "messages": int(row.messages),
            "user_messages": user_messages,
            "assistant_messages": int(row.assistant_messages or 0),
            "avg_user_msg_chars": round(float(row.avg_user_msg_chars), 2)
            if row.avg_user_msg_chars is not None
            else None,
            "question_ratio": round(int(row.user_question_messages or 0) / user_messages, 4)
            if user_messages
            else None,
            "active_days": int(row.active_days),
            "messages_by_source": by_source.get(row.epoch, {}),
        }
        epoch_start = _epoch_start_from_label(row.epoch)
        profile_row = existing.get(epoch_start)
        if profile_row is None:
            db.add(
                EpochProfile(
                    epoch_start=epoch_start,
                    epoch_kind="month",
                    source_slug=None,
                    stats=stats,
                )
            )
        elif profile_row.stats != stats:
            profile_row.stats = stats  # profile (LLM) field intentionally preserved
        stats_out.append(stats)

    await db.flush()
    log.info("temporal.epoch_stats_computed", extra={"epochs": len(stats_out)})
    return stats_out


# ---------------------------------------------------------------------------
# 2. Epoch profiles (scaffold tier, cached)
# ---------------------------------------------------------------------------

_PROFILE_SYSTEM = (
    "You characterise one month of a person's AI-conversation history from a sample "
    "of their own messages. Be specific and non-flattering; describe, don't praise. "
    "Respond with a single JSON object only."
)

_PROFILE_SCHEMA_HINT = (
    '{"themes": ["max 6 short strings"], "focus": "one sentence", '
    '"sophistication": 0.0, "delegation": 0.0, "valence": 0.0, "shifts": "string"}'
)


def build_epoch_profile_prompt(epoch: str, stats: dict, samples: list[str]) -> str:
    """User prompt for one epoch's scaffold-tier profile call."""
    lines = [
        f"Epoch: {epoch} (one calendar month).",
        f"Deterministic stats: {json.dumps(stats, separators=(',', ':'))}",
        f"Sample of the person's own messages that month ({len(samples)} shown, "
        f"each truncated to {_PROFILE_MSG_CHARS} chars, in chronological order):",
    ]
    lines += [f"- {s}" for s in samples]
    lines += [
        "",
        "Return JSON with exactly these keys:",
        "- themes: up to 6 short strings (dominant topics/activities)",
        "- focus: 1 sentence — what this month was about",
        "- sophistication: float 0-1 (conceptual depth/precision of the person's asks)",
        "- delegation: float 0-1 (how much is delegated to the AI vs. self-done)",
        "- valence: float -1..1 (emotional tone of the person's messages)",
        "- shifts: 1-2 sentences — what changed this month vs. a typical month",
    ]
    return "\n".join(lines)


def parse_epoch_profile(raw: dict) -> dict:
    """Validate/clamp a raw LLM epoch-profile payload into the stored shape."""
    themes_raw = raw.get("themes")
    themes = [str(t)[:80] for t in themes_raw[:6]] if isinstance(themes_raw, list) else []
    return {
        "themes": themes,
        "focus": str(raw.get("focus") or "")[:500],
        "sophistication": _clamp(raw.get("sophistication"), 0.0, 1.0),
        "delegation": _clamp(raw.get("delegation"), 0.0, 1.0),
        "valence": _clamp(raw.get("valence"), -1.0, 1.0),
        "shifts": str(raw.get("shifts") or "")[:500],
    }


async def _sample_epoch_user_messages(db: AsyncSession, epoch: str) -> list[str]:
    """Up to 40 user messages for the month, spread evenly, truncated to 300 chars."""
    rows = (
        await db.execute(
            select(Message.content)
            .where(
                Message.role == "user",
                Message.message_at.is_not(None),
                func.strftime("%Y-%m", Message.message_at) == epoch,
            )
            .order_by(Message.message_at)
        )
    ).all()
    contents = [r.content for r in rows if r.content and r.content.strip()]
    if len(contents) > _PROFILE_SAMPLE_MAX:
        step = len(contents) / _PROFILE_SAMPLE_MAX
        contents = [contents[int(i * step)] for i in range(_PROFILE_SAMPLE_MAX)]
    return [c.strip()[:_PROFILE_MSG_CHARS] for c in contents]


async def profile_epochs(
    db: AsyncSession, *, fable: bool | None = None, force: bool = False
) -> int:
    """Profile every epoch lacking a cached LLM profile (or all, if forced).

    One scaffold-tier ``chat_json`` call per epoch, bounded to
    ``_PROFILE_CONCURRENCY`` concurrent calls (llm.py applies its own global
    semaphore on top). DB reads/writes stay on this session's task; only the
    LLM calls run concurrently. Returns the number of epochs profiled.
    """
    q = select(EpochProfile).where(
        EpochProfile.epoch_kind == "month",
        EpochProfile.source_slug.is_(None),
    )
    if not force:
        q = q.where(EpochProfile.profile.is_(None))
    epochs = (await db.execute(q.order_by(EpochProfile.epoch_start))).scalars().all()
    if not epochs:
        return 0

    # Phase 1 — sequential DB sampling (AsyncSession is not concurrency-safe).
    prompts: list[tuple[EpochProfile, str]] = []
    for row in epochs:
        epoch = _epoch_label(row.epoch_start)
        samples = await _sample_epoch_user_messages(db, epoch)
        if not samples:
            continue
        prompts.append((row, build_epoch_profile_prompt(epoch, row.stats, samples)))

    # Phase 2 — bounded-concurrency LLM calls (pure, no DB access).
    gate = asyncio.Semaphore(_PROFILE_CONCURRENCY)

    async def _call(user_prompt: str) -> dict:
        async with gate:
            return await chat_json(
                system=_PROFILE_SYSTEM,
                user=user_prompt,
                schema_hint=_PROFILE_SCHEMA_HINT,
                temperature=0.3,
                max_tokens=1024,
                tier="scaffold",
                fable=fable,
            )

    results = await asyncio.gather(
        *(_call(p) for _, p in prompts), return_exceptions=True
    )

    # Phase 3 — sequential persistence.
    model = resolve_model("scaffold", fable)
    profiled = 0
    first_error: BaseException | None = None
    for (row, _), result in zip(prompts, results):
        if isinstance(result, BaseException):
            first_error = first_error or result
            log.warning(
                "temporal.epoch_profile_failed",
                extra={"epoch": _epoch_label(row.epoch_start), "error": str(result)[:200]},
            )
            continue
        row.profile = parse_epoch_profile(result)
        row.model_used = model
        profiled += 1

    await db.flush()
    log.info(
        "temporal.epochs_profiled",
        extra={"requested": len(prompts), "profiled": profiled, "model": model},
    )
    if profiled == 0 and first_error is not None:
        raise first_error  # nothing succeeded — surface the cause (e.g. LLMUnavailable)
    return profiled


# ---------------------------------------------------------------------------
# 3. Trajectory synthesis (hard tier)
# ---------------------------------------------------------------------------

_TRAJECTORY_SYSTEM = (
    "You are a careful longitudinal analyst. You receive observed per-month metric "
    "series from a person's AI-conversation history. You extrapolate each metric "
    "exactly 2 months forward with honest confidence bands, and you reason about "
    "what the trajectory shapes imply. Never alter observed values. Respond with a "
    "single JSON object only."
)


def build_observed_series(epochs: list[EpochProfile]) -> dict[str, list[dict]]:
    """Observed per-metric series from stats + cached profiles; <2 points → skipped."""
    observed: dict[str, list[dict]] = {}
    for metric in _STAT_METRICS + _PROFILE_METRICS:
        points: list[dict] = []
        for row in epochs:
            if metric in _STAT_METRICS:
                value = (row.stats or {}).get(metric)
            else:
                value = (row.profile or {}).get(metric)
            if value is None:
                continue
            points.append(
                {"epoch": _epoch_label(row.epoch_start), "value": float(value), "kind": "observed"}
            )
        if len(points) >= 2:
            observed[metric] = points
    return observed


def build_trajectory_prompt(observed: dict[str, list[dict]]) -> str:
    """User prompt for the single hard-tier trajectory synthesis call."""
    tables = {
        metric: [[p["epoch"], p["value"]] for p in points]
        for metric, points in observed.items()
    }
    return "\n".join(
        [
            "Observed monthly series (epoch, value) per metric:",
            json.dumps(tables, separators=(",", ":")),
            "",
            "For EACH metric return:",
            '- "series": the observed points VERBATIM (epoch, value, kind="observed"), '
            f"then EXACTLY {_EXTRAPOLATED_POINTS} future epochs with "
            'kind="extrapolated", each with "ci_low" and "ci_high" (a confidence band '
            "around value, wider for the second point).",
            '- "narrative": 1-2 sentences on the trajectory of that metric.',
            "Also return:",
            '- "assumptions": a global list of short strings — the assumptions your '
            "extrapolations rest on.",
            '- "abstraction": 2-4 sentences on what the combined trajectory shapes imply '
            "about how this person's thinking is changing — a deeper pattern, not a "
            "restatement of the numbers.",
            "",
            "Return JSON exactly matching:",
            '{"metrics": {"<metric>": {"series": [{"epoch": "YYYY-MM", "value": 0.0, '
            '"kind": "observed|extrapolated", "ci_low": 0.0, "ci_high": 0.0}], '
            '"narrative": "..."}}, "assumptions": ["..."], "abstraction": "..."}',
        ]
    )


def _fallback_extrapolation(points: list[dict], steps: int) -> list[dict]:
    """Deterministic linear extrapolation with a widening band (model-drift fallback)."""
    last, prev = points[-1], points[-2] if len(points) >= 2 else points[-1]
    slope = last["value"] - prev["value"]
    spread = max(abs(slope), abs(last["value"]) * 0.1, 1e-6)
    out = []
    for i in range(1, steps + 1):
        value = last["value"] + slope * i
        out.append(
            {
                "epoch": _next_epoch_label(last["epoch"], i),
                "value": round(value, 4),
                "kind": "extrapolated",
                "ci_low": round(value - spread * i, 4),
                "ci_high": round(value + spread * i, 4),
            }
        )
    return out


def parse_trajectory_response(
    raw: dict, observed: dict[str, list[dict]]
) -> tuple[dict[str, dict], list[str], str]:
    """Defensively validate the hard-tier payload against the observed input.

    - Observed points are taken from the *input* verbatim (any model drift on
      observed values is discarded).
    - Exactly 2 extrapolated points per metric, on the 2 epochs following the
      last observed one; missing/invalid ones are replaced by a deterministic
      linear fallback and the band is forced to bracket the value.
    """
    metrics_raw = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    parsed: dict[str, dict] = {}

    for metric, obs_points in observed.items():
        entry = metrics_raw.get(metric) if isinstance(metrics_raw.get(metric), dict) else {}
        model_series = entry.get("series") if isinstance(entry.get("series"), list) else []
        expected_epochs = [
            _next_epoch_label(obs_points[-1]["epoch"], i)
            for i in range(1, _EXTRAPOLATED_POINTS + 1)
        ]

        extrapolated: list[dict] = []
        for point in model_series:
            if not isinstance(point, dict) or point.get("kind") != "extrapolated":
                continue
            epoch = str(point.get("epoch") or "")
            if not _EPOCH_RE.match(epoch):
                continue
            try:
                value = float(point["value"])
            except (KeyError, TypeError, ValueError):
                continue
            ci_low = _clamp(point.get("ci_low"), -1e12, 1e12, default=value)
            ci_high = _clamp(point.get("ci_high"), -1e12, 1e12, default=value)
            if ci_low > ci_high:
                ci_low, ci_high = ci_high, ci_low
            extrapolated.append(
                {
                    "epoch": epoch,
                    "value": value,
                    "kind": "extrapolated",
                    "ci_low": min(ci_low, value),
                    "ci_high": max(ci_high, value),
                }
            )

        # Force the expected future epochs, in order; fall back deterministically.
        fallback = _fallback_extrapolation(obs_points, _EXTRAPOLATED_POINTS)
        by_epoch = {p["epoch"]: p for p in extrapolated}
        final_extrapolated = [
            by_epoch.get(epoch, fallback[i]) | {"epoch": epoch}
            for i, epoch in enumerate(expected_epochs)
        ]

        narrative = str(entry.get("narrative") or "")[:1000] or None
        parsed[metric] = {
            "series": [dict(p) for p in obs_points] + final_extrapolated,
            "narrative": narrative,
        }

    assumptions_raw = raw.get("assumptions")
    assumptions = (
        [str(a)[:300] for a in assumptions_raw[:12]]
        if isinstance(assumptions_raw, list)
        else []
    )
    abstraction = str(raw.get("abstraction") or "")[:2000]
    return parsed, assumptions, abstraction


async def synthesize_trajectories(
    db: AsyncSession, *, fable: bool | None = None, report_id: int | None = None
) -> list[Trajectory]:
    """Synthesize observed+extrapolated trajectories via ONE hard-tier call.

    Persists one ``Trajectory`` row per metric plus a ``__abstraction__`` row
    holding the global abstraction narrative and assumptions. When
    ``report_id`` is None, prior standalone rows (``report_id IS NULL``) are
    replaced (latest-wins). Empty corpus → empty list, no LLM call.
    """
    epochs = (
        (
            await db.execute(
                select(EpochProfile)
                .where(
                    EpochProfile.epoch_kind == "month",
                    EpochProfile.source_slug.is_(None),
                )
                .order_by(EpochProfile.epoch_start)
            )
        )
        .scalars()
        .all()
    )
    observed = build_observed_series(epochs)
    if not observed:
        log.info("temporal.trajectories_skipped", extra={"reason": "no observed series"})
        return []

    raw = await chat_json(
        system=_TRAJECTORY_SYSTEM,
        user=build_trajectory_prompt(observed),
        temperature=0.2,
        max_tokens=4096,
        tier="hard",
        fable=fable,
    )
    parsed, assumptions, abstraction = parse_trajectory_response(raw, observed)
    model = resolve_model("hard", fable)

    if report_id is None:
        await db.execute(delete(Trajectory).where(Trajectory.report_id.is_(None)))

    rows: list[Trajectory] = []
    for metric in _STAT_METRICS + _PROFILE_METRICS:
        if metric not in parsed:
            continue
        rows.append(
            Trajectory(
                report_id=report_id,
                metric=metric,
                series=parsed[metric]["series"],
                narrative=parsed[metric]["narrative"],
                assumptions=None,
                model_used=model,
            )
        )
    rows.append(
        Trajectory(
            report_id=report_id,
            metric=ABSTRACTION_METRIC,
            series=[],
            narrative=abstraction or None,
            assumptions=assumptions or None,
            model_used=model,
        )
    )
    db.add_all(rows)
    await db.flush()
    log.info(
        "temporal.trajectories_synthesized",
        extra={"metrics": len(rows) - 1, "model": model, "report_id": report_id},
    )
    return rows
