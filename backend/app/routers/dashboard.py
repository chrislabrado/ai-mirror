from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation import Conversation, Source
from app.models.message import Message
from app.models.report import Report
from app.schemas.common import GaugeSet
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> DashboardSummary:
    """Powers the top-right LAST MIRROR RUN panel and the three speedometer gauges."""

    total_conv = (await db.execute(select(func.count()).select_from(Conversation))).scalar_one()
    total_msg = (await db.execute(select(func.count()).select_from(Message))).scalar_one()

    src_rows = (
        await db.execute(
            select(
                Source.slug, Source.display_name, func.count(Conversation.id).label("count")
            )
            .join(Conversation, Conversation.source_id == Source.id, isouter=True)
            .group_by(Source.id)
        )
    ).all()
    sources = [
        {"slug": r.slug, "name": r.display_name, "conversations": int(r.count or 0)}
        for r in src_rows
    ]

    # The LAST MIRROR RUN panel is for full-corpus analyses that produce
    # bullets + gauges. Deep-dives and Focus Lens results are stored as
    # `Report` rows too, but they have no gauges and should not displace
    # the mirror summary on the dashboard.
    last_report = (
        await db.execute(
            select(Report)
            .where(Report.kind.in_(("full_mirror", "advanced_abstract")))
            .order_by(Report.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last_report is None:
        return DashboardSummary(
            last_run_at=None,
            last_run_kind=None,
            bullets=[
                "No analysis runs yet.",
                "Ingest a conversation export to begin.",
                "Open the Export Guide for per-platform steps.",
            ],
            gauges=None,
            total_conversations=int(total_conv),
            total_messages=int(total_msg),
            sources=sources,
        )

    gauges = GaugeSet(**last_report.gauges) if last_report.gauges else None
    bullets: list[str] = []
    if last_report.summary:
        bullets = [b.strip("•- ").strip() for b in last_report.summary.splitlines() if b.strip()][:5]

    return DashboardSummary(
        last_run_at=last_report.created_at,
        last_run_kind=last_report.kind,
        bullets=bullets or [last_report.title],
        gauges=gauges,
        total_conversations=int(total_conv),
        total_messages=int(total_msg),
        sources=sources,
    )
