from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .domain import AgentContext, AuditEvent, Artifact, ArtifactSummary, LLMProvider, NovelProject, ProjectInput, ProjectNotFoundError, ProjectRepository, PromptStore, TaskRecord, TaskStatus, TaskStore, WorkflowStep, utc_now
from .workflow_spec import WORKFLOW_STEPS, workflow_dependency_map


WORKFLOW_ORDER = [step.key for step in WORKFLOW_STEPS]
WORKFLOW_CHILDREN: dict[str, set[str]] = {}

for step_key, dependencies in workflow_dependency_map().items():
    for dependency in dependencies:
        WORKFLOW_CHILDREN.setdefault(dependency, set()).add(step_key)


def _project_step_from_artifacts(artifacts: dict[str, Artifact]) -> WorkflowStep:
    for step_key in reversed(WORKFLOW_ORDER):
        if step_key in artifacts:
            return WorkflowStep(step_key)
    return WorkflowStep.CREATED


def _dependent_step_keys(step_key: str) -> list[str]:
    removed: list[str] = []
    stack = list(WORKFLOW_CHILDREN.get(step_key, set()))
    seen: set[str] = set()

    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        removed.append(current)
        stack.extend(WORKFLOW_CHILDREN.get(current, set()))

    removed.sort(key=lambda key: WORKFLOW_ORDER.index(key) if key in WORKFLOW_ORDER else len(WORKFLOW_ORDER))
    return removed


@dataclass(frozen=True)
class PromptService:
    store: PromptStore

    def load(self, template_name: str) -> str:
        return self.store.load(template_name)

    def render(self, template_name: str, variables: Mapping[str, Any]) -> str:
        template = self.load(template_name)
        return template.format(**variables)


@dataclass(frozen=True)
class LLMService:
    provider: LLMProvider

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1200,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        return self.provider.complete(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )


@dataclass
class ProjectService:
    repository: ProjectRepository

    def create(self, project_input: ProjectInput) -> NovelProject:
        project = NovelProject(input=project_input)
        return self.repository.save(project)

    def get(self, project_id: str) -> NovelProject:
        project = self.repository.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def list(self) -> list[NovelProject]:
        return self.repository.list()

    def save(self, project: NovelProject) -> NovelProject:
        project.touch()
        return self.repository.save(project)

    def delete(self, project_id: str) -> NovelProject:
        project = self.repository.delete(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def add_artifact(self, project_id: str, artifact: Artifact, step: Any | None = None) -> NovelProject:
        project = self.get(project_id)
        project.add_artifact(artifact)
        if step is not None:
            project.current_step = step
            project.status = step
        return self.save(project)

    def remove_artifact(self, project_id: str, artifact_key: str) -> tuple[NovelProject, list[str]]:
        project = self.get(project_id)
        removed: list[str] = []

        if project.remove_artifact(artifact_key) is not None:
            removed.append(artifact_key)

        for dependent_key in _dependent_step_keys(artifact_key):
            if project.remove_artifact(dependent_key) is not None:
                removed.append(dependent_key)

        if not removed:
            raise LookupError(f"artifact not found: {project_id}/{artifact_key}")

        project.status = _project_step_from_artifacts(project.artifacts)
        project.current_step = project.status
        return self.save(project), removed


@dataclass
class AuditService:
    sink: Any | None = None

    def record(
        self,
        action: str,
        *,
        project_id: str | None = None,
        actor: str = "system",
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self.sink is None:
            return
        self.sink.write(
            AuditEvent(
                action=action,
                project_id=project_id,
                actor=actor,
                message=message,
                payload=payload or {},
            )
        )


@dataclass
class TaskService:
    store: TaskStore
    executor: ThreadPoolExecutor
    default_timeout_seconds: int = 600
    _futures: dict[str, Future[Any]] | None = None

    def __post_init__(self) -> None:
        if self._futures is None:
            self._futures = {}

    def submit(
        self,
        project_id: str,
        task_name: str,
        job: Callable[[], Any],
    ) -> TaskRecord:
        task = self.store.create(TaskRecord(project_id=project_id, task_name=task_name))

        def runner() -> Any:
            task.started_at = utc_now()
            task.status = TaskStatus.RUNNING
            self.store.update(task)
            try:
                result = job()
                task.status = TaskStatus.COMPLETED
                task.result = result if isinstance(result, dict) else {"value": result}
                return result
            except Exception as exc:  # pragma: no cover - surfaces in task state
                task.status = TaskStatus.FAILED
                task.error = str(exc)
                raise
            finally:
                task.finished_at = utc_now()
                self.store.update(task)

        future = self.executor.submit(runner)
        self._futures[task.task_id] = future
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        return self.store.get(task_id)

    def list(self, project_id: str | None = None) -> list[TaskRecord]:
        return self.store.list(project_id)

    def cancel(self, task_id: str) -> TaskRecord | None:
        future = self._futures.get(task_id) if self._futures is not None else None
        task = self.store.get(task_id)
        if task is None:
            return None
        if future is not None and future.cancel():
            task.status = TaskStatus.CANCELLED
            task.finished_at = utc_now()
            self.store.update(task)
        return task

    def delete_project(self, project_id: str) -> int:
        task_ids = [task.task_id for task in self.store.list(project_id)]
        removed = self.store.delete_by_project(project_id)
        for task_id in task_ids:
            future = self._futures.get(task_id) if self._futures is not None else None
            if future is not None:
                future.cancel()
                self._futures.pop(task_id, None)
        return removed


def artifact_excerpt(content: str, *, head_chars: int = 800, tail_chars: int = 200) -> str:
    text = content.strip()
    if len(text) <= head_chars + tail_chars + 20:
        return text
    return f"{text[:head_chars].rstrip()}\n…\n{text[-tail_chars:].lstrip()}"


def compact_artifact_context(artifact: Artifact, *, excerpt_chars: int = 1000, include_excerpt: bool = True) -> dict[str, Any]:
    excerpt_head = max(int(excerpt_chars * 0.8), 200)
    excerpt_tail = max(excerpt_chars - excerpt_head, 120)
    context = {
        "key": artifact.key,
        "title": artifact.title,
        "summary": artifact.summary.model_dump(mode="json"),
        "metadata": artifact.metadata,
    }
    if include_excerpt:
        context["content_excerpt"] = artifact_excerpt(artifact.content, head_chars=excerpt_head, tail_chars=excerpt_tail)
    return context


def compact_artifacts_context(artifacts: dict[str, Artifact], *, excerpt_chars: int = 1000, include_excerpt: bool = True) -> dict[str, Any]:
    return {
        key: compact_artifact_context(artifact, excerpt_chars=excerpt_chars, include_excerpt=include_excerpt)
        for key, artifact in artifacts.items()
    }


def build_artifact(
    key: str,
    title: str,
    content: str,
    summary: ArtifactSummary | dict[str, Any] | None = None,
    **metadata: Any,
) -> Artifact:
    artifact_summary = summary
    if artifact_summary is None:
        artifact_summary = ArtifactSummary()
    elif isinstance(artifact_summary, dict):
        artifact_summary = ArtifactSummary.model_validate(artifact_summary)
    return Artifact(key=key, title=title, content=content, summary=artifact_summary, metadata=metadata)


def agent_context(project_id: str, payload: Mapping[str, Any]) -> AgentContext:
    return AgentContext(
        project_id=project_id,
        temperature=float(payload.get("temperature", 0.7)),
        max_tokens=int(payload.get("max_tokens", 1200)),
        payload=dict(payload),
    )
