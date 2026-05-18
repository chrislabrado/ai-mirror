from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Entity(Base):
    """A knowledge-graph node extracted from messages.

    Backed by Neo4j when available; this table is the SQLite fallback
    triple-store and an index of canonical entities.
    """

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_label_kind", "label", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(256), index=True)
    kind: Mapped[str] = mapped_column(String(64))  # concept | person | tool | project | belief | trait
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    salience: Mapped[float] = mapped_column(Float, default=0.0)
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    outgoing: Mapped[list["Relationship"]] = relationship(
        back_populates="subject",
        foreign_keys="Relationship.subject_id",
        cascade="all, delete-orphan",
    )
    incoming: Mapped[list["Relationship"]] = relationship(
        back_populates="object_",
        foreign_keys="Relationship.object_id",
        cascade="all, delete-orphan",
    )


class Relationship(Base):
    """A typed edge between two entities (subject -[predicate]-> object)."""

    __tablename__ = "relationships"
    __table_args__ = (
        Index("ix_relationships_predicate", "predicate"),
        Index("ix_relationships_subject_object", "subject_id", "object_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    object_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    predicate: Mapped[str] = mapped_column(String(128))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    subject: Mapped[Entity] = relationship(
        back_populates="outgoing", foreign_keys=[subject_id]
    )
    object_: Mapped[Entity] = relationship(
        back_populates="incoming", foreign_keys=[object_id]
    )
