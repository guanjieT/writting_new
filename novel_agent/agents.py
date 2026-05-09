from __future__ import annotations

import json
from json import JSONDecodeError
from dataclasses import dataclass
from typing import Any

from .agent_helpers import artifact_prompt_context, build_outline_targets_json, chapter_plan_focus_from_context, normalize_text_list
from .domain import AgentContext, AgentOutput, ArtifactSummary, GeneratedArtifactPayload, NovelProject, WorkflowStep
from .context_builder import build_generation_context
from .services import LLMService, PromptService, build_artifact
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


def _require_keys(step: str, structured: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in structured]
    if missing:
        raise ValueError(f"{step} structured payload is missing required fields: {', '.join(missing)}")


def _normalize_structured_payload(step: str, payload: GeneratedArtifactPayload) -> None:
    structured = dict(payload.structured or {})
    if step != "rough_chapter_plan":
        payload.structured = structured
        return

    chapters = structured.get("chapters")
    if isinstance(chapters, list):
        if not structured.get("total_target_chapters"):
            structured["total_target_chapters"] = len(chapters)
        normalized_chapters: list[Any] = []
        for position, chapter in enumerate(chapters, start=1):
            if not isinstance(chapter, dict):
                normalized_chapters.append(chapter)
                continue
            normalized_chapter = dict(chapter)
            chapter_index = normalized_chapter.get("chapter_index", normalized_chapter.get("index"))
            if chapter_index in (None, ""):
                chapter_index = position
            normalized_chapter["chapter_index"] = chapter_index
            normalized_chapters.append(normalized_chapter)
        structured["chapters"] = normalized_chapters

    payload.structured = structured


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
            "knowledge_base_json": json.dumps(generation_context["knowledge_base"], ensure_ascii=False, indent=2),
            "recent_context_json": json.dumps(generation_context["recent_chapter_artifacts"], ensure_ascii=False, indent=2),
            "artifacts_json": json.dumps(generation_context["selected_artifacts"], ensure_ascii=False, indent=2),
            "step_payload_json": step_payload_json,
            "context_json": json.dumps({
                "step": generation_context["step"],
                "context_type": generation_context["context_type"],
                "project_brief": generation_context["project_brief"],
                "step_payload": generation_context["step_payload"],
                "knowledge_base": generation_context["knowledge_base"],
                "recent_chapter_artifacts": generation_context["recent_chapter_artifacts"],
            }, ensure_ascii=False, indent=2),
            "chapter_plan_focus_json": "{}",
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
        _normalize_structured_payload(self.step.value, generated_payload)
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
                variables["parent_artifact_json"] = json.dumps(artifact_prompt_context(parent_artifact, excerpt_chars=0), ensure_ascii=False, indent=2)
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
                "core_roles": normalize_text_list(payload.get("core_roles")),
                "role_slots": normalize_text_list(payload.get("role_slots")),
                "role_rules": normalize_text_list(payload.get("role_rules")),
                "notes": normalize_text_list(payload.get("notes")),
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
        variables["outline_targets_json"] = build_outline_targets_json(project, context)
        return variables


class RoughVolumeOutlineAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("rough_volume_outline", WorkflowStep.ROUGH_VOLUME_OUTLINE, "rough_volume_outline", "rough_volume_outline", "粗卷纲", WorkflowStep.OUTLINE)

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        variables["outline_targets_json"] = build_outline_targets_json(project, context)
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


class ChapterAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("chapter", WorkflowStep.CHAPTER, "chapter", "chapter", "章节草稿", WorkflowStep.CHAPTER_PLAN)

    def _recommended_max_tokens(self, context: AgentContext) -> int:
        try:
            target_words = int(context.payload.get("target_words") or 2000)
        except (TypeError, ValueError):
            target_words = 2000
        return min(max(target_words * 2, 3200), 6000)

    def _content_char_length(self, content: str) -> int:
        return len(content.strip())

    def _check_content_length(self, content: str, context: AgentContext) -> tuple[bool, int, int]:
        target_words = int(context.payload.get("target_words") or 2000)
        threshold = max(int(target_words * 0.85), target_words - 300)
        actual = self._content_char_length(content)
        ok = actual >= threshold
        return ok, actual, threshold

    def _build_expansion_prompt(
        self,
        project: NovelProject,
        context: AgentContext,
        first_draft: str,
        system_prompt: str,
        max_tokens: int,
    ) -> str:
        target_words = int(context.payload.get("target_words") or 2000)
        min_words = max(int(target_words * 0.85), target_words - 300)
        return (
            f"你上一次生成的正文长度明显不足（实际约 {{actual_len}} 字，目标 {{target_words}} 字，最低要求 {{min_words}} 字）。"
            f"现在不要改写章节目标，不要改变关键事件顺序，不要重置叙事，而是在现有章节计划基础上把本章扩写为完整可读的小说正文。\n\n"
            f"扩写要求：\n"
            f"- 保留原有 main_event、conflict、hook\n"
            f"- 保留原有 scene 顺序\n"
            f"- 通过动作、对白、心理反应、环境互动、局势变化来扩写\n"
            f"- 不允许用总结、说明、复盘来凑字数\n"
            f"- 不允许新增会影响后续规划的大设定\n"
            f"- 目标长度：至少接近 {target_words} 字，宁可略长，不可明显偏短\n\n"
            f"上一次生成的正文草稿（参考用，不要原文复制）：\n{{first_draft}}\n\n"
            f"请输出一个 JSON 对象，content 必须是扩写后的完整章节正文（目标 {target_words} 字以上）。JSON："
        )

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        parent_artifact_json = variables.get("parent_artifact_json", "{}")
        try:
            parent_context = json.loads(parent_artifact_json)
        except JSONDecodeError:
            parent_context = {}
        if not isinstance(parent_context, dict):
            parent_context = {}
        variables["chapter_plan_focus_json"] = json.dumps(
            chapter_plan_focus_from_context(parent_context),
            ensure_ascii=False,
            indent=2,
        )
        target_words = int(context.payload.get("target_words") or 2000)
        variables["target_words_85"] = max(int(target_words * 0.85), target_words - 300)
        return variables

    def run(self, project: NovelProject, context: AgentContext, deps: AgentDependencies) -> AgentOutput:
        if context.max_tokens <= 1600:
            context = context.model_copy(update={"max_tokens": self._recommended_max_tokens(context)})
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

        ok, actual, threshold = self._check_content_length(content, context)
        if not ok:
            expansion_prompt_template = self._build_expansion_prompt(
                project, context, content, system_prompt, context.max_tokens
            )
            expansion_prompt = expansion_prompt_template.format(
                actual_len=actual,
                target_words=int(context.payload.get("target_words") or 2000),
                min_words=threshold,
                first_draft=content[:1000],
            )
            raw_retry = deps.llm_service.complete(
                expansion_prompt,
                system_prompt=system_prompt,
                temperature=context.temperature,
                max_tokens=context.max_tokens,
                metadata={"artifact_key": self.artifact_key, "artifact_title": self.artifact_title},
            )
            payload = self._parse_generated_payload(raw_retry)
            content = payload.content.strip()
            if not content:
                raise ValueError("LLM returned empty content after retry")
            ok_retry, actual_retry, threshold_retry = self._check_content_length(content, context)
            if not ok_retry:
                raise ValueError(
                    f"正文长度不足（补救后仍不达标）：目标字数 {int(context.payload.get('target_words') or 2000)}，"
                    f"最低阈值 {threshold_retry}，实际 {actual_retry}，当前 max_tokens {context.max_tokens}。"
                    f"建议：提高 max_tokens 后重试。"
                )

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
