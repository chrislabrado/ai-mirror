from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Report(Base):
    """A generated analysis report (Full Mirror, Advanced Abstract, Focus Lens).

    Reports are stored as modular JSON blocks via :class:`ReportBlock`.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    # full_mirror | advanced_abstract | focus_lens
    title: Mapped[str] = mapped_column(String(512))
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    gauges: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    blocks: Mapped[list["ReportBlock"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportBlock.position",
    )


class ReportBlock(Base):
    """A reusable, modular JSON section of a report."""

    __tablename__ = "report_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    block_type: Mapped[str] = mapped_column(String(64))
    # e.g. cognitive_style | strengths | weaknesses | aptitudes | neurodivergence_signals
    heading: Mapped[str | None] = mapped_column(String(256), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    body_markdown: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    report: Mapped[Report] = relationship(back_populates="blocks")
