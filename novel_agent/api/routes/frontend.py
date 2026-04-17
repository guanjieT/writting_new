from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["frontend"])

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


def _page(page_name: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / page_name, media_type="text/html; charset=utf-8")


@router.get("/", include_in_schema=False)
def index_page() -> FileResponse:
    return _page("index.html")


@router.get("/workflow", include_in_schema=False)
def workflow_page() -> FileResponse:
    return _page("workflow.html")


@router.get("/outline", include_in_schema=False)
def outline_page() -> FileResponse:
    return _page("outline.html")


@router.get("/review", include_in_schema=False)
def review_page() -> FileResponse:
    return _page("review.html")
