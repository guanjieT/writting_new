from __future__ import annotations

import json
from typing import Any

from .context_builder import build_generation_context
from .domain import AgentContext, NovelProject, WorkflowStep
from .services import compact_artifact_context


CHAPTER_PLAN_FOCUS_KEYS: tuple[str, ...] = (
    "volume_index",
    "chapter_index",
    "title",
    "summary",
    "chapter_type",
    "pov_character",
    "main_event",
    "conflict",
    "hook",
    "target_words",
    "min_words",
    "characters",
    "introduced_characters",
    "scene_summaries",
    "continuity_notes",
    "writing_notes",
)


def normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def build_outline_targets_json(project: NovelProject, context: AgentContext) -> str:
    generation_context = build_generation_context(project, WorkflowStep.OUTLINE.value, context.payload)
    project_input = generation_context["project_input"]
    step_payload = generation_context["step_payload"]
    target_volume_count = int(step_payload.get("volume_count") or project_input.get("target_volume_count") or 1)
    target_chapters_per_volume = int(step_payload.get("chapters_per_volume") or project_input.get("target_chapters_per_volume") or 12)
    return json.dumps(
        {
            "target_volume_count": target_volume_count,
            "target_chapters_per_volume": target_chapters_per_volume,
            "target_words": int(project_input.get("target_words") or 0),
        },
        ensure_ascii=False,
        indent=2,
    )


def artifact_prompt_context(artifact: Any, *, excerpt_chars: int = 0) -> dict[str, Any]:
    context = compact_artifact_context(artifact, excerpt_chars=excerpt_chars, include_excerpt=excerpt_chars > 0)
    summary = context.get("summary")
    if isinstance(summary, dict):
        structured = summary.get("structured")
        if isinstance(structured, dict):
            context["structured"] = structured
    return context


def chapter_plan_focus_from_context(parent_context: dict[str, Any]) -> dict[str, Any]:
    summary = parent_context.get("summary")
    summary_payload = summary if isinstance(summary, dict) else {}
    structured = parent_context.get("structured")
    if not isinstance(structured, dict):
        structured = summary_payload.get("structured")
    structured_payload = structured if isinstance(structured, dict) else {}
    focused_structured = {
        key: structured_payload.get(key)
        for key in CHAPTER_PLAN_FOCUS_KEYS
        if key in structured_payload
    }
    return {
        "key": parent_context.get("key", ""),
        "title": parent_context.get("title", ""),
        "metadata": parent_context.get("metadata", {}),
        "overview": summary_payload.get("overview") or summary_payload.get("summary", ""),
        "structured": focused_structured,
    }
