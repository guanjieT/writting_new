from __future__ import annotations

from fastapi import APIRouter, Depends

from ...domain import TaskNotFoundError, TaskRecord
from ..deps import get_container
from ..schemas import (
    ChapterRequest,
    CharacterRequest,
    ConsistencyRequest,
    MemoryRequest,
    OutlineRequest,
    RequirementsRequest,
    RevisionRequest,
    StoryBibleRequest,
    TaskResponse,
)
from ...services import task_scope_from_payload

router = APIRouter(tags=["workflow-steps"])


def _submit_step(container, project_id: str, step: str, payload: dict) -> TaskRecord:
    return container.task_service.submit(
        project_id=project_id,
        task_name=step,
        scope=task_scope_from_payload(step, payload),
        input_payload=payload,
        job=lambda: container.orchestrator.dispatch(project_id, step, payload).model_dump(mode="json"),
    )


@router.post("/projects/{project_id}/requirements", response_model=TaskResponse)
def generate_requirements(project_id: str, payload: RequirementsRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "requirements", payload.model_dump())


@router.post("/projects/{project_id}/story-bible", response_model=TaskResponse)
def generate_story_bible(project_id: str, payload: StoryBibleRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "story_bible", payload.model_dump())


@router.post("/projects/{project_id}/characters", response_model=TaskResponse)
def generate_characters(project_id: str, payload: CharacterRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "characters", payload.model_dump())


@router.post("/projects/{project_id}/outline", response_model=TaskResponse)
def generate_outline(project_id: str, payload: OutlineRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "outline", payload.model_dump())


@router.post("/projects/{project_id}/chapters", response_model=TaskResponse)
def generate_chapter(project_id: str, payload: ChapterRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "chapter", payload.model_dump())


@router.post("/projects/{project_id}/revision", response_model=TaskResponse)
def generate_revision(project_id: str, payload: RevisionRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "revision", payload.model_dump())


@router.post("/projects/{project_id}/consistency", response_model=TaskResponse)
def generate_consistency(project_id: str, payload: ConsistencyRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "consistency", payload.model_dump())


@router.post("/projects/{project_id}/memory", response_model=TaskResponse)
def generate_memory(project_id: str, payload: MemoryRequest, container=Depends(get_container)) -> TaskRecord:
    return _submit_step(container, project_id, "memory", payload.model_dump())


@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
def list_project_tasks(project_id: str, container=Depends(get_container)) -> list[TaskRecord]:
    return container.task_service.list(project_id)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, container=Depends(get_container)) -> TaskRecord:
    task = container.task_service.get(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: str, container=Depends(get_container)) -> TaskRecord:
    task = container.task_service.cancel(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task
