from __future__ import annotations

from fastapi import APIRouter, Depends

from ...domain import TaskRecord
from ..deps import get_container
from ..schemas import ChapterPlanRequest, RoughChapterPlanRequest, RoughVolumeOutlineRequest, TaskResponse, VolumeOutlineRequest

router = APIRouter(prefix="/projects", tags=["planning"])


def _submit_step(container, project_id: str, step: str, payload: dict) -> TaskRecord:
    return container.task_service.submit(
        project_id=project_id,
        task_name=step,
        job=lambda: container.orchestrator.dispatch(project_id, step, payload).model_dump(mode="json"),
    )


@router.post("/{project_id}/volume-outline", response_model=TaskResponse)
def generate_volume_outline(project_id: str, payload: VolumeOutlineRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "volume_outline", payload.model_dump())


@router.post("/{project_id}/rough-volume-outline", response_model=TaskResponse)
def generate_rough_volume_outline(project_id: str, payload: RoughVolumeOutlineRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "rough_volume_outline", payload.model_dump())


@router.post("/{project_id}/rough-chapter-plan", response_model=TaskResponse)
def generate_rough_chapter_plan(project_id: str, payload: RoughChapterPlanRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "rough_chapter_plan", payload.model_dump())


@router.post("/{project_id}/chapter-plan", response_model=TaskResponse)
def generate_chapter_plan(project_id: str, payload: ChapterPlanRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "chapter_plan", payload.model_dump())