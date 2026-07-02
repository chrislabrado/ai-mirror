from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.report import Report
from app.schemas.common import GaugeSet, ReportBlockOut
from app.schemas.reports import (
    MetaAnalysisRequest,
    ReportListItem,
    ReportListResponse,
    ReportRequest,
    ReportResponse,
)
from app.services.reports import run_advanced_abstract, run_full_mirror, run_meta_analysis

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/full-mirror", response_model=ReportResponse)
async def full_mirror(
    payload: ReportRequest,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Generate the comprehensive Full Mirror Analysis report."""
    return await run_full_mirror(db=db, request=payload)


@router.post("/advanced-abstract", response_model=ReportResponse)
async def advanced_abstract(
    payload: ReportRequest,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Generate the Advanced Abstract Analysis report."""
    return await run_advanced_abstract(db=db, request=payload)


@router.post("/meta-analysis", response_model=ReportResponse)
async def meta_analysis(
    payload: MetaAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Compare the last N Full Mirror runs: stability vs drift vs model noise."""
    return await run_meta_analysis(db=db, request=payload)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    kind: Literal["full_mirror", "advanced_abstract", "focus_lens", "deep_dive", "meta_analysis"] | None = Query(
        default=None, description="Optional report kind filter."
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    """Paginated list of reports ordered by created_at DESC."""
    base_q = select(Report)
    if kind is not None:
        base_q = base_q.where(Report.kind == kind)

    total: int = (
        await db.execute(select(func.count()).select_from(base_q.subquery()))
    ).scalar_one()

    rows_q = base_q.order_by(Report.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(rows_q)
    reports = result.scalars().all()

    items = [
        ReportListItem(
            id=r.id,
            kind=r.kind,
            title=r.title,
            summary=r.summary,
            model_used=r.model_used,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return ReportListResponse(items=items, total=total)


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return s or "report"


@router.get("/{report_id}/markdown", response_class=Response)
async def get_report_markdown(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the report as a single concatenated Markdown document.

    Triggers a browser download via Content-Disposition. This is the
    canonical Full Mirror deliverable from the original spec — every
    section as one self-contained .md file the user can archive.
    """
    result = await db.execute(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.blocks))
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    kind_label = (report.kind or "report").replace("_", " ").title()
    lines: list[str] = []
    lines.append(f"# {report.title}")
    lines.append("")
    lines.append(
        f"_{kind_label} · generated {report.created_at.isoformat(timespec='seconds')}"
        + (f" · model {report.model_used}" if report.model_used else "")
        + "_"
    )
    lines.append("")

    if report.gauges:
        try:
            g = GaugeSet(**report.gauges)
            lines.append("## Gauges")
            lines.append("")
            lines.append(f"- **Thought Clarity** — {round(g.thought_clarity * 100)} / 100")
            lines.append(
                f"- **Self-Reflection Depth** — {round(g.self_reflection_depth * 100)} / 100"
            )
            lines.append(f"- **Aptitude Balance** — {round(g.aptitude_balance * 100)} / 100")
            lines.append("")
        except Exception:  # noqa: BLE001
            pass

    if report.summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(report.summary.strip())
        lines.append("")

    for block in sorted(report.blocks, key=lambda b: b.position):
        heading = (block.heading or block.block_type.replace("_", " ").title()).strip()
        lines.append(f"## {heading}")
        lines.append("")
        body = (block.body_markdown or "").strip()
        # Demote any in-body headings by one level so they don't collide
        # with the section heading we just emitted.
        body = re.sub(r"(?m)^(#{1,3})\s", lambda m: ("#" * (len(m.group(1)) + 1)) + " ", body)
        lines.append(body)
        lines.append("")
        if block.evidence:
            lines.append("**Evidence:**")
            lines.append("")
            for ev in block.evidence:
                if not isinstance(ev, dict):
                    continue
                snippet = (ev.get("snippet") or "").strip()
                source = ev.get("source_slug") or "—"
                at = ev.get("message_at") or ""
                snippet_short = (snippet[:300] + "…") if len(snippet) > 300 else snippet
                lines.append(f"- _[{source} · {at}]_ {snippet_short}")
            lines.append("")

    lines.append("")
    lines.append(f"_Report id: {report.id}_")
    body_md = "\n".join(lines)

    filename = (
        f"ai-mirror-{_slugify(report.kind)}-{report.id}-"
        f"{report.created_at.strftime('%Y%m%d-%H%M')}.md"
    )
    return Response(
        content=body_md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Full report detail including all blocks."""
    result = await db.execute(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.blocks))
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    gauges: GaugeSet | None = None
    if report.gauges:
        try:
            gauges = GaugeSet(**report.gauges)
        except Exception:  # noqa: BLE001
            gauges = None

    blocks = [
        ReportBlockOut(
            id=b.id,
            block_type=b.block_type,
            heading=b.heading,
            position=b.position,
            body_markdown=b.body_markdown,
            structured=b.structured,
            evidence=b.evidence,
        )
        for b in sorted(report.blocks, key=lambda b: b.position)
    ]

    return ReportResponse(
        report_id=report.id,
        kind=report.kind,
        title=report.title,
        summary=report.summary or "",
        gauges=gauges,
        blocks=blocks,
        model_used=report.model_used,
        created_at=report.created_at,
    )
