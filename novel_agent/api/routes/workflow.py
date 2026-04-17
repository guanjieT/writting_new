from __future__ import annotations

from fastapi import APIRouter

from ...workflow_spec import workflow_spec

router = APIRouter(tags=["workflow"])


@router.get("/workflow/spec")
def get_workflow_spec() -> dict[str, object]:
    return workflow_spec()