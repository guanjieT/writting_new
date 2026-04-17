from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_container
from ..schemas import ErrorResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, str])
def health(container=Depends(get_container)) -> dict[str, str]:
    return {"status": "ok", "app": container.config.app_name}
