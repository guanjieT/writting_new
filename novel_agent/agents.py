from __future__ import annotations

import json
from json import JSONDecodeError
from dataclasses import dataclass
from typing import Any

from .domain import AgentContext, AgentOutput, ArtifactSummary, GeneratedArtifactPayload, NovelProject, WorkflowStep
from .context_builder import build_generation_context
from .services import LLMService, PromptService, build_artifact, compact_artifact_context
from .workflow_spec import workflow_dependent_map


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


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
            return ["outline", "chapter_plan", "consistency"]
        if step_key == "outline":
            return ["volume_outline", "chapter_plan"]
        if step_key == "volume_outline":
            return ["chapter_plan", "chapter"]
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
        return GeneratedArtifactPayload.model_validate(payload)

    def _build_summary(self, payload: GeneratedArtifactPayload) -> ArtifactSummary:
        summary = ArtifactSummary(
            overview=payload.overview.strip(),
            key_facts=[str(item).strip() for item in payload.key_facts if str(item).strip()],
            constraints=[str(item).strip() for item in payload.constraints if str(item).strip()],
            open_questions=[str(item).strip() for item in payload.open_questions if str(item).strip()],
            best_for_steps=self._best_for_steps(),
            best_for_reason=payload.best_for_reason.strip(),
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
        artifact = build_artifact(
            self.artifact_key,
            self.artifact_title,
            content,
            summary=summary,
            agent=self.name,
            step=self.step.value,
            generated_payload=payload.model_dump(mode="json"),
        )
        return AgentOutput(step=self.step, artifact=artifact, notes=[f"generated by {self.name}"])


@dataclass
class PlanningAgent(BaseAgent):
    parent_step: WorkflowStep | None = None

    def build_variables(self, project: NovelProject, context: AgentContext) -> dict[str, Any]:
        variables = super().build_variables(project, context)
        if self.parent_step is not None:
            parent_artifact = project.artifacts.get(self.parent_step.value)
            if parent_artifact is not None:
                variables["parent_artifact_json"] = json.dumps(compact_artifact_context(parent_artifact, excerpt_chars=220, include_excerpt=True), ensure_ascii=False, indent=2)
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
        generation_context = build_generation_context(project, self.step.value, context.payload)
        project_input = generation_context["project_input"]
        step_payload = generation_context["step_payload"]
        target_volume_count = int(step_payload.get("volume_count") or project_input.get("target_volume_count") or 1)
        target_chapters_per_volume = int(step_payload.get("chapters_per_volume") or project_input.get("target_chapters_per_volume") or 12)
        variables["outline_targets_json"] = json.dumps(
            {
                "target_volume_count": target_volume_count,
                "target_chapters_per_volume": target_chapters_per_volume,
                "target_words": int(project_input.get("target_words") or 0),
            },
            ensure_ascii=False,
            indent=2,
        )
        return variables


class VolumeOutlineAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("volume_outline", WorkflowStep.VOLUME_OUTLINE, "volume_outline", "volume_outline", "卷纲设计", WorkflowStep.OUTLINE)


class ChapterPlanAgent(PlanningAgent):
    def __init__(self) -> None:
        super().__init__("chapter_plan", WorkflowStep.CHAPTER_PLAN, "chapter_plan", "chapter_plan", "章节计划", WorkflowStep.VOLUME_OUTLINE)


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
        VolumeOutlineAgent(),
        ChapterPlanAgent(),
        ChapterAgent(),
        RevisionAgent(),
        ConsistencyAgent(),
        MemoryAgent(),
    ]
    return {agent.step.value: agent for agent in agents}
