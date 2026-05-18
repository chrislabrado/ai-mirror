from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.focus_lens import FocusLensRequest, FocusLensResponse
from app.services.reports import run_focus_lens

router = APIRouter(prefix="/focus-lens", tags=["focus-lens"])


@router.post("", response_model=FocusLensResponse)
async def focus_lens(
    payload: FocusLensRequest,
    db: AsyncSession = Depends(get_db),
) -> FocusLensResponse:
    """Natural-language selective analysis with parsed filters and hybrid retrieval."""
    return await run_focus_lens(db=db, request=payload)
