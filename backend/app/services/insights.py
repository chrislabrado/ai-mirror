"""Insights aggregation service.

Groups ReportBlock rows by block_type and surfaces occurrence counts,
a sample body snippet, and the most recent report reference.
"""
from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportBlock
from app.schemas.insights import AggregatedBlock, InsightsAggregated

_SAMPLE_BODY_MAX = 600


async def get_aggregated_insights(db: AsyncSession) -> InsightsAggregated:
    """Aggregate ReportBlock rows across all reports.

    Returns occurrence counts per block_type, ordered by
    occurrence_count DESC then latest_created_at DESC.
    """
    # Total reports
    total_reports: int = (
        await db.execute(select(func.count()).select_from(Report))
    ).scalar_one()

    # Total blocks
    total_blocks: int = (
        await db.execute(select(func.count()).select_from(ReportBlock))
    ).scalar_one()

    if total_blocks == 0:
        return InsightsAggregated(
            total_reports=total_reports,
            total_blocks=0,
            blocks=[],
        )

    # Distinct block_types
    bt_result = await db.execute(
        select(ReportBlock.block_type).distinct()
    )
    block_types: list[str] = [row[0] for row in bt_result.all()]

    aggregated: list[AggregatedBlock] = []

    for block_type in block_types:
        # Count rows for this block_type
        count_result = await db.execute(
            select(func.count())
            .select_from(ReportBlock)
            .where(ReportBlock.block_type == block_type)
        )
        occurrence_count: int = count_result.scalar_one()

        # Most recent block of this type (joined to Report for created_at)
        latest_result = await db.execute(
            select(ReportBlock, Report)
            .join(Report, ReportBlock.report_id == Report.id)
            .where(ReportBlock.block_type == block_type)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        row = latest_result.first()
        if row is None:
            continue

        latest_block, latest_report = row
        heading: str | None = latest_block.heading

        # Determine sample_body: prefer structured heading if available,
        # fall back to body_markdown truncated to _SAMPLE_BODY_MAX chars
        sample_body = latest_block.body_markdown[:_SAMPLE_BODY_MAX]

        aggregated.append(
            AggregatedBlock(
                block_type=block_type,
                heading=heading,
                occurrence_count=occurrence_count,
                sample_body=sample_body,
                latest_report_id=latest_report.id,
                latest_created_at=latest_report.created_at,
            )
        )

    # Sort: occurrence_count DESC, latest_created_at DESC
    aggregated.sort(
        key=lambda ab: (ab.occurrence_count, ab.latest_created_at),
        reverse=True,
    )

    return InsightsAggregated(
        total_reports=total_reports,
        total_blocks=total_blocks,
        blocks=aggregated,
    )
