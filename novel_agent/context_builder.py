from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .domain import NovelProject
from .services import compact_artifact_context


def _project_brief(project: NovelProject) -> dict[str, Any]:
    project_input = project.input
    return {
        "project_id": project.project_id,
        "title": project_input.title,
        "genre": project_input.genre,
        "stage": project.status.value,
        "premise": project_input.premise,
        "target_words": project_input.target_words,
        "target_volume_count": project_input.target_volume_count,
        "target_chapters_per_volume": project_input.target_chapters_per_volume,
        "target_audience": project_input.target_audience,
        "tone": list(project_input.tone),
        "style": list(project_input.style),
        "outline_focus": list(project_input.outline_focus),
        "core_requirements": list(project_input.core_requirements),
        "forbidden_elements": list(project_input.forbidden_elements),
    }


def _project_input_payload(project: NovelProject) -> dict[str, Any]:
    return project.input.model_dump(mode="json")


def _step_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_payload = payload.get("payload")
    if isinstance(raw_payload, Mapping):
        return {key: value for key, value in raw_payload.items() if key not in {"temperature", "max_tokens"}}
    return {
        key: value
        for key, value in payload.items()
        if key not in {"temperature", "max_tokens", "payload"}
    }


def _selected_artifacts(project: NovelProject, step_keys: list[str], *, excerpt_chars: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for step_key in step_keys:
        artifact = project.artifacts.get(step_key)
        if artifact is None:
            continue
        result[step_key] = compact_artifact_context(artifact, excerpt_chars=excerpt_chars, include_excerpt=excerpt_chars > 0)
    return result


@dataclass(frozen=True)
class GenerationContextProfile:
    name: str
    artifact_keys: tuple[str, ...]
    artifact_excerpt_chars: int = 0
    context_type: str = "general"


GENERATION_CONTEXT_PROFILES: dict[str, GenerationContextProfile] = {
    "requirements": GenerationContextProfile("requirements", (), context_type="short"),
    "story_bible": GenerationContextProfile("story_bible", ("requirements",), artifact_excerpt_chars=160, context_type="short"),
    "characters": GenerationContextProfile("characters", ("requirements", "story_bible"), artifact_excerpt_chars=160, context_type="short"),
    "outline": GenerationContextProfile("outline", ("requirements", "story_bible", "characters"), artifact_excerpt_chars=0, context_type="brief"),
    "volume_outline": GenerationContextProfile("volume_outline", ("outline", "requirements"), artifact_excerpt_chars=220, context_type="expanded"),
    "chapter_plan": GenerationContextProfile("chapter_plan", ("volume_outline", "outline", "story_bible", "characters"), artifact_excerpt_chars=180, context_type="expanded"),
    "chapter": GenerationContextProfile("chapter", ("chapter_plan", "volume_outline", "outline"), artifact_excerpt_chars=260, context_type="expanded"),
    "revision": GenerationContextProfile("revision", ("chapter", "chapter_plan"), artifact_excerpt_chars=220, context_type="focused"),
    "consistency": GenerationContextProfile("consistency", ("chapter", "chapter_plan", "story_bible", "characters"), artifact_excerpt_chars=180, context_type="focused"),
    "memory": GenerationContextProfile("memory", ("chapter", "revision", "consistency"), artifact_excerpt_chars=140, context_type="focused"),
}


def build_generation_context(project: NovelProject, step: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    profile = GENERATION_CONTEXT_PROFILES.get(step, GenerationContextProfile(step, ()))
    return {
        "step": step,
        "context_type": profile.context_type,
        "project_brief": _project_brief(project),
        "project_input": _project_input_payload(project),
        "step_payload": _step_payload(payload),
        "selected_artifacts": _selected_artifacts(project, list(profile.artifact_keys), excerpt_chars=profile.artifact_excerpt_chars),
    }


def build_completion_context(project: NovelProject, payload: Mapping[str, Any], direct_dependency_steps: list[str]) -> dict[str, Any]:
    selected_artifacts = _selected_artifacts(project, direct_dependency_steps, excerpt_chars=180)
    field_context = {
        "key": str(payload.get("field_key", "")),
        "label": str(payload.get("field_label", "")),
        "type": str(payload.get("field_type", "text")),
        "placeholder": str(payload.get("field_placeholder", "")),
        "current_value": str(payload.get("current_value", "")),
    }
    return {
        "step": str(payload.get("step", "")),
        "field": field_context,
        "step_payload": _step_payload(payload),
        "direct_dependency_steps": direct_dependency_steps,
        "direct_dependency_artifacts": selected_artifacts,
        "project_brief": _project_brief(project),
        "project_input": _project_input_payload(project),
    }


def build_stage_summary(project: NovelProject, step: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    context = build_generation_context(project, step, payload)
    return {
        "project_brief": context["project_brief"],
        "project_input": context["project_input"],
        "step_payload": context["step_payload"],
        "selected_artifacts": context["selected_artifacts"],
        "context_type": context["context_type"],
    }