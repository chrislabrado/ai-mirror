from __future__ import annotations

from fastapi import APIRouter

from app.schemas.export_guide import ExportGuide
from app.services.export_guide_content import build_export_guide

router = APIRouter(prefix="/export-guide", tags=["export-guide"])


@router.get("", response_model=ExportGuide)
async def export_guide() -> ExportGuide:
    """Latest (2026) per-platform export instructions consumed by the Export Guide page."""
    return build_export_guide()
