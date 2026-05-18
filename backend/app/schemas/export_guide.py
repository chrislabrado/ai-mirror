from __future__ import annotations

from pydantic import BaseModel


class ExportStep(BaseModel):
    n: int
    text: str


class ExportPlatform(BaseModel):
    slug: str
    name: str
    icon: str
    summary: str
    steps: list[ExportStep]
    output_formats: list[str]
    notes: list[str] = []
    docs_url: str | None = None


class ExportGuide(BaseModel):
    version: str
    last_updated: str
    intro: str
    footer_note: str
    platforms: list[ExportPlatform]
