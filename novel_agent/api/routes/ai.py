from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from ...domain import NovelProject
from ...workflow_spec import workflow_dependency_map
from ...context_builder import build_completion_context
from ..deps import get_container
from ..schemas import FieldCompletionRequest, FieldCompletionResponse

router = APIRouter(prefix="/projects/{project_id}", tags=["ai"])


def _clean_completion(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return text.strip()


def _completion_context(project: NovelProject, payload: FieldCompletionRequest) -> dict[str, object]:
    completion_payload = payload.model_dump(mode="json")
    return build_completion_context(project, completion_payload, workflow_dependency_map().get(payload.step, []))


@router.post("/field-completion", response_model=FieldCompletionResponse)
def complete_field(project_id: str, payload: FieldCompletionRequest, container=Depends(get_container)) -> dict[str, str]:
    project: NovelProject = container.orchestrator.get_project(project_id)
    completion_context = _completion_context(project, payload)
    prompt = container.prompt_service.render(
        "field_completion",
        {
            "project_summary": project.summary(),
            "step_label": payload.step_label or payload.step,
            "step_description": payload.step_description or "",
            "field_label": payload.field_label,
            "field_type": payload.field_type,
            "field_placeholder": payload.field_placeholder or "",
            "current_value": payload.current_value or "",
            "field_context_json": json.dumps(completion_context["field"], ensure_ascii=False, indent=2),
            "step_payload_json": json.dumps(completion_context["step_payload"], ensure_ascii=False, indent=2),
            "direct_dependency_steps_json": json.dumps(completion_context["direct_dependency_steps"], ensure_ascii=False, indent=2),
            "direct_dependency_artifacts_json": json.dumps(completion_context["direct_dependency_artifacts"], ensure_ascii=False, indent=2),
            "input_json": json.dumps(completion_context["project_input"], ensure_ascii=False, indent=2),
            "project_brief_json": json.dumps(completion_context["project_brief"], ensure_ascii=False, indent=2),
        },
    )
    completion = container.llm_service.complete(
        prompt,
        system_prompt="你是一个只输出字段内容的小说参数补全助手。",
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        metadata={
            "project_id": project_id,
            "step": payload.step,
            "field_key": payload.field_key,
            "field_label": payload.field_label,
        },
    )
    suggestion = _clean_completion(completion)
    container.audit_service.record(
        action="project.field_completed",
        project_id=project_id,
        payload={"step": payload.step, "field_key": payload.field_key, "field_label": payload.field_label},
    )
    return {"step": payload.step, "field_key": payload.field_key, "suggestion": suggestion}