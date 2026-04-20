from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from .agents import AgentDependencies, BaseAgent, build_agent_registry
from .domain import AgentOutput, NovelProject, UnsupportedStepError, WorkflowOrderError, WorkflowStep
from .workflow_spec import workflow_dependency_map
from .services import AuditService, ProjectService, agent_context, _artifact_scope_payload, _scope_matches


def _to_chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value <= 10:
        return "十" if value == 10 else digits[value]
    if value < 20:
        return f"十{digits[value - 10]}" if value > 10 else "十"
    tens, ones = divmod(value, 10)
    prefix = f"{digits[tens]}十" if tens > 1 else "十"
    return f"{prefix}{digits[ones]}" if ones else prefix


@dataclass
class NovelOrchestrator:
    project_service: ProjectService
    audit_service: AuditService
    agent_dependencies: AgentDependencies
    agents: dict[str, BaseAgent]

    @classmethod
    def build(cls, project_service: ProjectService, audit_service: AuditService, agent_dependencies: AgentDependencies) -> "NovelOrchestrator":
        return cls(
            project_service=project_service,
            audit_service=audit_service,
            agent_dependencies=agent_dependencies,
            agents=build_agent_registry(),
        )

    def get_project(self, project_id: str) -> NovelProject:
        return self.project_service.get(project_id)

    def list_projects(self) -> list[NovelProject]:
        return self.project_service.list()

    def dispatch(self, project_id: str, step: str, payload: Mapping[str, Any]) -> AgentOutput:
        project = self.get_project(project_id)
        if step not in self.agents:
            raise UnsupportedStepError(step)

        self._ensure_step_ready(project, step, payload)

        context = agent_context(project_id, payload)
        output = self.agents[step].run(project, context, self.agent_dependencies)
        project, stale_keys = self.project_service.register_generated_artifact(project_id, output.artifact)
        self.audit_service.record(
            action=f"agent.{step}.completed",
            project_id=project_id,
            message=output.artifact.title,
            payload={"artifact_key": output.artifact.key, "notes": output.notes, "stale_keys": stale_keys},
        )
        return output

    def create_project(self, project_input: Any) -> NovelProject:
        project = self.project_service.create(project_input)
        self.audit_service.record(action="project.created", project_id=project.project_id, payload={"title": project.input.title})
        return project

    def update_project(self, project_id: str, project_input: Any) -> NovelProject:
        project = self.get_project(project_id)
        project.input = project_input
        if project.artifacts:
            project.artifacts.clear()
            project.touch(WorkflowStep.CREATED)
        self.project_service.save(project)
        self.audit_service.record(
            action="project.updated",
            project_id=project_id,
            payload={"title": project.input.title, "genre": project.input.genre},
        )
        return project

    def project_snapshot(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        return {
            "project": project.model_dump(mode="json"),
            "artifacts": {key: artifact.model_dump(mode="json") for key, artifact in project.artifacts.items()},
        }

    def _ensure_step_ready(self, project: NovelProject, step: str, payload: Mapping[str, Any]) -> None:
        dependencies = workflow_dependency_map().get(step, [])
        missing: list[str] = []
        stale: list[str] = []
        for dependency in dependencies:
            dependency_scope = _artifact_scope_payload(dependency, payload)
            artifact = next((candidate for candidate in project.artifacts.values() if _scope_matches(candidate, dependency, dependency_scope)), None)
            if artifact is None:
                missing.append(dependency)
                continue
            if artifact.metadata.get("stale"):
                stale.append(dependency)
        if missing:
            raise WorkflowOrderError(f"step '{step}' requires: {', '.join(missing)}")
        if stale:
            raise WorkflowOrderError(f"step '{step}' depends on stale artifacts: {', '.join(stale)}")

        if step == "volume_outline":
            volume_index = max(int(payload.get("volume_index") or 1), 1)
            parent = next((candidate for candidate in project.artifacts.values() if _scope_matches(candidate, "rough_volume_outline", {"scope_kind": "project"})), None)
            if parent is None:
                raise WorkflowOrderError("step 'volume_outline' requires rough_volume_outline")
            if not self._artifact_contains_entry(parent.content, "卷", volume_index):
                raise WorkflowOrderError(f"rough_volume_outline is missing volume {volume_index}")

        if step == "chapter_plan":
            chapter_index = max(int(payload.get("chapter_index") or 1), 1)
            parent_scope = _artifact_scope_payload("rough_chapter_plan", payload)
            parent = next((candidate for candidate in project.artifacts.values() if _scope_matches(candidate, "rough_chapter_plan", parent_scope)), None)
            if parent is None:
                raise WorkflowOrderError("step 'chapter_plan' requires rough_chapter_plan")
            if not self._artifact_contains_entry(parent.content, "章", chapter_index):
                raise WorkflowOrderError(f"rough_chapter_plan is missing chapter {chapter_index}")

    def _artifact_contains_entry(self, content: str, unit: str, index: int) -> bool:
        text = str(content or "")
        patterns = [
            rf"^第{index}{unit}[:：]",
            rf"^第{index}个{unit}[:：]",
            rf"^第{_to_chinese_number(index)}{unit}[:：]",
        ]
        return any(re.search(pattern, text, re.MULTILINE) for pattern in patterns)
