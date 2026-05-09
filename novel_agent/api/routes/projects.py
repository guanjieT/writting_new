from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import PlainTextResponse

from ...domain import NovelProject
from ...quality import build_quality_report
from ...services import build_project_manuscript
from ..deps import get_container
from ..schemas import ProjectCreateRequest, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreateRequest, container=Depends(get_container)) -> NovelProject:
    return container.orchestrator.create_project(payload)


@router.get("", response_model=list[ProjectResponse])
def list_projects(container=Depends(get_container)) -> list[NovelProject]:
    return container.orchestrator.list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, container=Depends(get_container)) -> NovelProject:
    return container.orchestrator.get_project(project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, payload: ProjectCreateRequest, container=Depends(get_container)) -> NovelProject:
    return container.orchestrator.update_project(project_id, payload)


@router.get("/{project_id}/snapshot", response_model=dict[str, object])
def project_snapshot(project_id: str, container=Depends(get_container)) -> dict[str, object]:
    return container.orchestrator.project_snapshot(project_id)


@router.get("/{project_id}/exports/manuscript", response_class=PlainTextResponse)
def export_project_manuscript(project_id: str, container=Depends(get_container)) -> str:
    project = container.orchestrator.get_project(project_id)
    return build_project_manuscript(project)


@router.get("/{project_id}/quality-report", response_model=dict[str, object])
def project_quality_report(project_id: str, container=Depends(get_container)) -> dict[str, object]:
    project = container.orchestrator.get_project(project_id)
    return build_quality_report(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, container=Depends(get_container)) -> Response:
    project = container.project_service.get(project_id)
    container.project_service.delete(project_id)
    container.task_service.delete_project(project_id)
    container.audit_service.record(
        action="project.deleted",
        project_id=project_id,
        payload={"title": project.input.title, "genre": project.input.genre},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{project_id}/artifacts/{artifact_key}", status_code=status.HTTP_200_OK)
def delete_project_artifact(project_id: str, artifact_key: str, container=Depends(get_container)) -> dict[str, object]:
    project, removed_artifacts = container.project_service.remove_artifact(project_id, artifact_key)
    container.audit_service.record(
        action="project.artifact.deleted",
        project_id=project_id,
        payload={
            "artifact_key": artifact_key,
            "removed_artifacts": removed_artifacts,
            "current_step": project.current_step.value,
        },
    )
    return {
        "project_id": project_id,
        "artifact_key": artifact_key,
        "removed_artifacts": removed_artifacts,
        "current_step": project.current_step.value,
    }
