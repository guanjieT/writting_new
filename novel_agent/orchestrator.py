from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .agents import AgentDependencies, BaseAgent, build_agent_registry
from .domain import AgentOutput, NovelProject, UnsupportedStepError, WorkflowOrderError, WorkflowStep
from .workflow_spec import workflow_dependency_map
from .services import AuditService, ProjectService, agent_context


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

        self._ensure_step_ready(project, step)

        context = agent_context(project_id, payload)
        output = self.agents[step].run(project, context, self.agent_dependencies)
        project.add_artifact(output.artifact, output.step)
        self.project_service.save(project)
        self.audit_service.record(
            action=f"agent.{step}.completed",
            project_id=project_id,
            message=output.artifact.title,
            payload={"artifact_key": output.artifact.key, "notes": output.notes},
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

    def _ensure_step_ready(self, project: NovelProject, step: str) -> None:
        dependencies = workflow_dependency_map().get(step, [])
        missing = [dependency for dependency in dependencies if dependency not in project.artifacts]
        if missing:
            raise WorkflowOrderError(f"step '{step}' requires: {', '.join(missing)}")
