from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

DIST_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"


@router.get("/")
def frontend_index() -> FileResponse:
    return FileResponse(
        DIST_DIR / "index.html",
        media_type="text/html",
    )
