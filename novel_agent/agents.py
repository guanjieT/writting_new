from __future__ import annotations

import json
from json import JSONDecodeError
from dataclasses import dataclass
from typing import Any

from .domain import AgentContext, AgentOutput, ArtifactSummary, GeneratedArtifactPayload, NovelProject, WorkflowStep
from .context_builder import build_generation_context
from .services import LLMService, PromptService, build_artifact, compact_artifact_context
from .services import _artifact_key, _artifact_scope_payload, _scope_matches
from .workflow_spec import workflow_dependent_map


STRUCTURED_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "outline": ("story_arcs", "global_goals", "main_conflicts", "ending_direction", "volume_plan_hints"),
    "rough_volume_outline": ("volumes",),
    "volume_outline": ("volume_index", "title", "summary", "goal", "main_conflict", "ending_hook", "target_chapter_count", "target_words", "arc_segments"),
    "rough_chapter_plan": ("volume_index", "total_target_chapters", "chapters"),
    "chapter_plan": (
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
    ),
}


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _build_outline_targets_json(project: NovelProject, context: AgentContext) -> str:
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


def _artifact_prompt_context(artifact: Any, *, excerpt_chars: int = 0) -> dict[str, Any]:
    context = compact_artifact_context(artifact, excerpt_chars=excerpt_chars, include_excerpt=excerpt_chars > 0)
    summary = context.get("summary")
    if isinstance(summary, dict):
        structured = summary.get("structured")
        if isinstance(structured, dict):
            context["structured"] = structured
    return context


def _require_keys(step: str, structured: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in structured]
    if missing:
        raise ValueError(f"{step} structured payload is missing required fields: {', '.join(missing)}")


def _validate_chapter_sequence(step: str, structured: dict[str, Any]) -> None:
    chapters = structured.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError(f"{step} structured payload must include a non-empty chapters list")

    total_target_chapters = structured.get("total_target_chapters")
    try:
        total_target_chapters_int = int(total_target_chapters)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{step} structured payload must include an integer total_target_chapters") from exc
    if total_target_chapters_int <= 0:
        raise ValueError(f"{step} structured payload must include a positive total_target_chapters")

    if len(chapters) != total_target_chapters_int:
        raise ValueError(f"{step} chapters count mismatch: expected {total_target_chapters_int}, got {len(chapters)}")

    seen_indices: list[int] = []
    for position, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            raise ValueError(f"{step} chapters[{position - 1}] must be an object")
        chapter_index = chapter.get("chapter_index")
        if chapter_index is None:
            raise ValueError(f"{step} chapter at position {position} is missing chapter_index")
        try:
            chapter_index_int = int(chapter_index)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{step} chapter_index must be an integer at position {position}") from exc
        if chapter_index_int != position:
            raise ValueError(f"{step} chapter_index must be consecutive from 1 to {total_target_chapters_int}; found {chapter_index_int} at position {position}")
        seen_indices.append(chapter_index_int)

    if len(seen_indices) != len(set(seen_indices)):
        raise ValueError(f"{step} chapter_index values must be unique and consecutive from 1 to {total_target_chapters_int}")


def _validate_structured_payload(step: str, payload: GeneratedArtifactPayload) -> None:
    structured = payload.structured if isinstance(payload.structured, dict) else {}
    required_keys = STRUCTURED_REQUIRED_KEYS.get(step, ())
    if required_keys:
        _require_keys(step, structured, required_keys)

    if step == "rough_volume_outline":
        volumes = structured.get("volumes")
        if not isinstance(volumes, list) or not volumes:
            raise ValueError("rough_volume_outline structured payload must include a non-empty volumes list")
        seen_volume_indices: list[int] = []
        for position, volume in enumerate(volumes, start=1):
            if not isinstance(volume, dict):
                raise ValueError(f"rough_volume_outline volumes[{position - 1}] must be an object")
            volume_index = volume.get("volume_index")
            if volume_index is None:
                raise ValueError(f"rough_volume_outline volume at position {position} is missing volume_index")
            try:
                volume_index_int = int(volume_index)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"rough_volume_outline volume_index must be an integer at position {position}") from exc
            if volume_index_int != position:
                raise ValueError(f"rough_volume_outline volume_index must be consecutive from 1 to {len(volumes)}; found {volume_index_int} at position {position}")
            for key in ("title", "summary", "goal", "main_conflict", "ending_hook", "target_chapter_count", "target_words"):
                if key not in volume:
                    raise ValueError(f"rough_volume_outline volume {position} is missing {key}")
            seen_volume_indices.append(volume_index_int)
        if len(seen_volume_indices) != len(set(seen_volume_indices)):
            raise ValueError("rough_volume_outline volume_index values must be unique and consecutive")

    if step == "rough_chapter_plan":
        _validate_chapter_sequence(step, structured)
        for position, chapter in enumerate(structured.get("chapters", []), start=1):
            for key in ("title", "summary", "chapter_type", "pov_character", "main_event", "conflict", "hook", "target_words"):
                if key not in chapter:
                    raise ValueError(f"rough_chapter_plan chapter {position} is missing {key}")

    if step == "chapter_plan":
        for key in ("continuity_notes", "writing_notes"):
            if key not in structured:
                raise ValueError(f"chapter_plan structured payload is missing required field: {key}")


@dataclass(frozen=True)
class AgentDependencies:
    prompt_service: PromptService
    llm_service: LLMService


@dataclass
class BaseAgent:
    name: str
    step: WorkflowStep
    template_name: str
    artifact_key: str
    artifact_title: str

    def _best_for_steps(self) -> list[str]:
        step_key = self.step.value
        if step_key == "requirements":
            return ["story_bible", "characters"]
        if step_key == "story_bible":
            return ["characters", "outline"]
        if step_key == "characters":
            return ["outline", "rough_volume_outline", "consistency"]
        if step_key == "outline":
            return ["rough_volume_outline"]
        if step_key == "rough_volume_outline":
            return ["volume_outline"]
        if step_key == "volume_outline":
            return ["rough_chapter_plan"]
        if step_key == "rough_chapter_plan":
            return ["chapter_plan"]
        if step_key == "chapter_plan":
            return ["chapter", "revision", "consistency"]
        if step_key == "chapter":
            return ["revision", "consistency", "memory"]
        if step_key == "revision":
            return ["chapter", "consistency"]
        if step_key == "consistency":
            return ["revision", "memory"]
        if step_key == "memory":
            return ["chapter", "revision", "consistency"]
        return workflow_dependent_map().get(step_key, [])

    def _artifact_scope_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        scope_payload = _artifact_scope_payload(self.step.value, payload)
        metadata = {
            "step": self.step.value,
            "scope_kind": scope_payload.get("scope_kind", "project"),
            "stale": False,
            "state": "active",
        }
        if scope_payload.get("scope_kind") == "volume":
            metadata["volume_index"] = scope_payload["volume_index"]
        if scope_payload.get("scope_kind") == "chapter":
            metadata["volume_index"] = scope_payload["volume_index"]
            metadata["chapter_index"] = scope_payload["chapter_index"]
        return metadata

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        generation_context = build_generation_context(project, self.step.value, context.payload)
        step_payload_json = json.dumps(generation_context["step_payload"], ensure_ascii=False, indent=2)
        return {
            "project_summary": project.summary(),
            "input_json": json.dumps(generation_context["project_input"], ensure_ascii=False, indent=2),
            "project_brief_json": json.dumps(generation_context["project_brief"], ensure_ascii=False, indent=2),
            "artifacts_json": json.dumps(generation_context["selected_artifacts"], ensure_ascii=False, indent=2),
            "step_payload_json": step_payload_json,
            "context_json": json.dumps({
                "step": generation_context["step"],
                "context_type": generation_context["context_type"],
                "project_brief": generation_context["project_brief"],
                "step_payload": generation_context["step_payload"],
            }, ensure_ascii=False, indent=2),
        }

    def _strip_code_fence(self, raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return text

    def _parse_generated_payload(self, raw_text: str) -> GeneratedArtifactPayload:
        text = self._strip_code_fence(raw_text)
        if not text:
            raise ValueError(f"LLM returned an empty generation payload for {self.artifact_key}")
        try:
            payload = json.loads(text)
        except JSONDecodeError as exc:
            preview = text.replace("\n", " ")[:500]
            raise ValueError(f"LLM returned invalid JSON for {self.artifact_key}: {preview or '<empty>'}") from exc
        if not isinstance(payload, dict):
            raise ValueError("LLM returned a non-object generation payload")
        generated_payload = GeneratedArtifactPayload.model_validate(payload)
        _validate_structured_payload(self.step.value, generated_payload)
        return generated_payload

    def _build_summary(self, payload: GeneratedArtifactPayload) -> ArtifactSummary:
        summary = ArtifactSummary(
            overview=payload.overview.strip(),
            key_facts=[str(item).strip() for item in payload.key_facts if str(item).strip()],
            constraints=[str(item).strip() for item in payload.constraints if str(item).strip()],
            open_questions=[str(item).strip() for item in payload.open_questions if str(item).strip()],
            best_for_steps=self._best_for_steps(),
            best_for_reason=payload.best_for_reason.strip(),
            structured=dict(payload.structured or {}),
        )
        summary.summary = summary.overview
        return summary

    def run(self, project: NovelProject, context: AgentContext, deps: AgentDependencies) -> AgentOutput:
        system_prompt = deps.prompt_service.load(self.template_name)
        prompt = deps.prompt_service.render(self.template_name, self.build_variables(project, context))
        raw_output = deps.llm_service.complete(
            prompt,
            system_prompt=system_prompt,
            temperature=context.temperature,
            max_tokens=context.max_tokens,
            metadata={"artifact_key": self.artifact_key, "artifact_title": self.artifact_title},
        )
        payload = self._parse_generated_payload(raw_output)
        content = payload.content.strip()
        if not content:
            raise ValueError("LLM returned empty content")
        summary = self._build_summary(payload)
        step_payload = context.payload
        artifact_metadata = self._artifact_scope_metadata(step_payload)
        artifact = build_artifact(
            _artifact_key(self.step.value, artifact_metadata),
            self.artifact_title,
            content,
            summary=summary,
            agent=self.name,
            **artifact_metadata,
            generated_payload=payload.model_dump(mode="json"),
        )
        return AgentOutput(step=self.step, artifact=artifact, notes=[f"generated by {self.name}"])


@dataclass
class PlanningAgent(BaseAgent):
    parent_step: WorkflowStep | None = None

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        if self.parent_step is not None:
            base_artifact = context.payload.get("base_artifact") if isinstance(context.payload, dict) else None
            parent_artifact = None
            if isinstance(base_artifact, dict) and base_artifact:
                summary = base_artifact.get("artifact_summary") or {}
                parent_artifact = build_artifact(
                    str(base_artifact.get("artifact_key") or self.parent_step.value),
                    str(base_artifact.get("artifact_title") or ""),
                    str(base_artifact.get("artifact_content") or ""),
                    summary=summary,
                    **{
                        key: value
                        for key, value in dict(base_artifact.get("artifact_metadata") or {}).items()
                        if value is not None
                    },
                )
            if parent_artifact is None:
                parent_scope_payload = _artifact_scope_payload(self.parent_step.value, context.payload)
                parent_artifact = next(
                    (
                        artifact
                        for artifact in project.artifacts.values()
                        if _scope_matches(artifact, self.parent_step.value, parent_scope_payload)
                    ),
                    None,
                )
            if parent_artifact is not None:
                variables["parent_artifact_json"] = json.dumps(_artifact_prompt_context(parent_artifact, excerpt_chars=0), ensure_ascii=False, indent=2)
        return variables


class RequirementAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("requirement", WorkflowStep.REQUIREMENTS, "requirements", "requirements", "需求分析")


class StoryBibleAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("story_bible", WorkflowStep.STORY_BIBLE, "story_bible", "story_bible", "世界观设定")


class CharacterAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("character", WorkflowStep.CHARACTERS, "characters", "characters", "角色框架")

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        payload = context.payload
        variables["character_frame_json"] = json.dumps(
            {
                "role_capacity": int(payload.get("role_capacity", 4) or 4),
                "core_roles": _normalize_text_list(payload.get("core_roles")),
                "role_slots": _normalize_text_list(payload.get("role_slots")),
                "role_rules": _normalize_text_list(payload.get("role_rules")),
                "notes": _normalize_text_list(payload.get("notes")),
            },
            ensure_ascii=False,
            indent=2,
        )
        return variables


class OutlineAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("outline", WorkflowStep.OUTLINE, "outline", "outline", "总纲设计")

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        variables["outline_targets_json"] = _build_outline_targets_json(project, context)
        return variables


class RoughVolumeOutlineAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("rough_volume_outline", WorkflowStep.ROUGH_VOLUME_OUTLINE, "rough_volume_outline", "rough_volume_outline", "粗卷纲", WorkflowStep.OUTLINE)

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        variables["outline_targets_json"] = _build_outline_targets_json(project, context)
        return variables


class VolumeOutlineAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("volume_outline", WorkflowStep.VOLUME_OUTLINE, "volume_outline", "volume_outline", "卷纲设计", WorkflowStep.ROUGH_VOLUME_OUTLINE)


class RoughChapterPlanAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("rough_chapter_plan", WorkflowStep.ROUGH_CHAPTER_PLAN, "rough_chapter_plan", "rough_chapter_plan", "粗章纲", WorkflowStep.VOLUME_OUTLINE)


class ChapterPlanAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("chapter_plan", WorkflowStep.CHAPTER_PLAN, "chapter_plan", "chapter_plan", "章节计划", WorkflowStep.ROUGH_CHAPTER_PLAN)


class ChapterAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("chapter", WorkflowStep.CHAPTER, "chapter", "chapter", "章节草稿")


class RevisionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("revision", WorkflowStep.REVISION, "revision", "revision", "修订结果")


class ConsistencyAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("consistency", WorkflowStep.CONSISTENCY, "consistency", "consistency", "一致性检查")


class MemoryAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("memory", WorkflowStep.MEMORY, "memory", "memory", "记忆整理")


def build_agent_registry() -> dict[str, BaseAgent]:
    agents: list[BaseAgent] = [
        RequirementAgent(),
        StoryBibleAgent(),
        CharacterAgent(),
        OutlineAgent(),
        RoughVolumeOutlineAgent(),
        VolumeOutlineAgent(),
        RoughChapterPlanAgent(),
        ChapterPlanAgent(),
        ChapterAgent(),
        RevisionAgent(),
        ConsistencyAgent(),
        MemoryAgent(),
    ]
    return {agent.step.value: agent for agent in agents}
