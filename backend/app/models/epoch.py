from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EpochProfile(Base):
    """Per-epoch (month) aggregate: deterministic SQL stats + cached LLM profile.

    ``stats`` is always machine-computed (no LLM); ``profile`` is the cached
    scaffold-tier LLM characterisation of the epoch and may be NULL until
    profiling has run. ``source_slug`` is NULL for the all-sources scope.
    """

    __tablename__ = "epoch_profiles"
    __table_args__ = (
        UniqueConstraint("epoch_start", "epoch_kind", "source_slug", name="uq_epoch_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    epoch_start: Mapped[date] = mapped_column(Date, index=True)  # first day of the month
    epoch_kind: Mapped[str] = mapped_column(String(16), default="month")
    source_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)  # NULL = all sources
    stats: Mapped[dict] = mapped_column(JSON)  # deterministic aggregates
    # none_as_null: clearing the profile must yield SQL NULL so the
    # "lacking profile" query (`profile.is_(None)`) keeps matching.
    profile: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Trajectory(Base):
    """A per-metric observed + extrapolated series synthesized by the hard tier.

    ``series`` is a list of ``{epoch: "YYYY-MM", value: float, kind:
    "observed"|"extrapolated", ci_low?: float, ci_high?: float}`` — every
    synthetic point is explicitly marked ``extrapolated`` with a confidence
    band. Rows with ``report_id`` NULL form the "latest" standalone set.
    """

    __tablename__ = "trajectories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True, nullable=True
    )
    metric: Mapped[str] = mapped_column(String(64), index=True)
    series: Mapped[list] = mapped_column(JSON)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
