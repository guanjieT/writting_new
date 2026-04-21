from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .domain import AgentContext, AuditEvent, Artifact, ArtifactSummary, LLMProvider, NovelProject, ProjectInput, ProjectNotFoundError, ProjectRepository, PromptStore, TaskRecord, TaskStatus, TaskStore, WorkflowStep, utc_now
from .workflow_spec import WORKFLOW_STEPS, workflow_dependency_map


WORKFLOW_ORDER = [step.key for step in WORKFLOW_STEPS]
WORKFLOW_STEP_RANK = {step_key: index for index, step_key in enumerate(WORKFLOW_ORDER)}
WORKFLOW_CHILDREN: dict[str, set[str]] = {}
WORKFLOW_DESCENDANTS: dict[str, list[str]] = {}
WORKFLOW_SCOPE_KIND = {step.key: step.scope for step in WORKFLOW_STEPS}

for step_key, dependencies in workflow_dependency_map().items():
    for dependency in dependencies:
        WORKFLOW_CHILDREN.setdefault(dependency, set()).add(step_key)


def _build_descendants_map() -> dict[str, list[str]]:
    descendants: dict[str, list[str]] = {}
    for step_key in WORKFLOW_ORDER:
        seen: set[str] = set()
        stack = list(WORKFLOW_CHILDREN.get(step_key, set()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(WORKFLOW_CHILDREN.get(current, set()))
        descendants[step_key] = sorted(seen, key=lambda key: WORKFLOW_ORDER.index(key) if key in WORKFLOW_ORDER else len(WORKFLOW_ORDER))
    return descendants


WORKFLOW_DESCENDANTS = _build_descendants_map()


def _artifact_scope_kind(step_key: str) -> str:
    return WORKFLOW_SCOPE_KIND.get(step_key, "project")


def _artifact_scope_payload(step_key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    scope_kind = _artifact_scope_kind(step_key)
    if scope_kind == "volume":
        return {"scope_kind": scope_kind, "volume_index": max(int(payload.get("volume_index") or 1), 1)}
    if scope_kind == "chapter":
        return {
            "scope_kind": scope_kind,
            "volume_index": max(int(payload.get("volume_index") or 1), 1),
            "chapter_index": max(int(payload.get("chapter_index") or 1), 1),
        }
    return {"scope_kind": "project"}


def _artifact_key(step_key: str, scope_payload: Mapping[str, Any]) -> str:
    scope_kind = scope_payload.get("scope_kind", "project")
    if scope_kind == "volume":
        return f"{step_key}:{scope_payload['volume_index']}"
    if scope_kind == "chapter":
        return f"{step_key}:{scope_payload['volume_index']}:{scope_payload['chapter_index']}"
    return step_key


def _scope_matches(artifact: Artifact, step_key: str, scope_payload: Mapping[str, Any]) -> bool:
    metadata = artifact.metadata or {}
    if metadata.get("step") != step_key:
        return False
    scope_kind = scope_payload.get("scope_kind", "project")
    if scope_kind != metadata.get("scope_kind", "project"):
        return False
    if scope_kind == "volume":
        return int(metadata.get("volume_index") or 0) == int(scope_payload.get("volume_index") or 0)
    if scope_kind == "chapter":
        return int(metadata.get("volume_index") or 0) == int(scope_payload.get("volume_index") or 0) and int(metadata.get("chapter_index") or 0) == int(scope_payload.get("chapter_index") or 0)
    return True


def _artifact_matches_descendant_scope(artifact: Artifact, step_key: str, scope_payload: Mapping[str, Any]) -> bool:
    if artifact.metadata.get("step") not in WORKFLOW_DESCENDANTS.get(step_key, []):
        return False
    scope_kind = scope_payload.get("scope_kind", "project")
    if scope_kind == "project":
        return True
    if scope_kind == "volume":
        return int(artifact.metadata.get("volume_index") or 0) == int(scope_payload.get("volume_index") or 0)
    if scope_kind == "chapter":
        return int(artifact.metadata.get("volume_index") or 0) == int(scope_payload.get("volume_index") or 0) and int(artifact.metadata.get("chapter_index") or 0) == int(scope_payload.get("chapter_index") or 0)
    return False


def _artifact_step_key(artifact: Artifact) -> str:
    metadata_step = str(artifact.metadata.get("step") or "").strip()
    if metadata_step:
        return metadata_step
    return str(artifact.key).split(":", 1)[0]


def _project_step_from_artifacts(artifacts: dict[str, Artifact]) -> WorkflowStep:
    latest_step = WorkflowStep.CREATED
    latest_rank = -1
    for artifact in artifacts.values():
        step_key = _artifact_step_key(artifact)
        step_rank = WORKFLOW_STEP_RANK.get(step_key)
        if step_rank is None or step_rank < latest_rank:
            continue
        latest_step = WorkflowStep(step_key)
        latest_rank = step_rank
    if latest_rank >= 0:
        return latest_step
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

    def _mark_descendants_stale(self, project: NovelProject, artifact: Artifact) -> list[str]:
        step_key = _artifact_step_key(artifact)
        scope_payload = {
            "scope_kind": artifact.metadata.get("scope_kind", "project"),
            "volume_index": artifact.metadata.get("volume_index"),
            "chapter_index": artifact.metadata.get("chapter_index"),
        }
        affected: list[str] = []
        for artifact_key, candidate in project.artifacts.items():
            if candidate.key == artifact.key:
                continue
            if not _artifact_matches_descendant_scope(candidate, step_key, scope_payload):
                continue
            if candidate.metadata.get("stale"):
                continue
            candidate.metadata = {**candidate.metadata, "stale": True, "state": "stale"}
            affected.append(artifact_key)
        return affected

    def register_generated_artifact(self, project_id: str, artifact: Artifact) -> tuple[NovelProject, list[str]]:
        project = self.get(project_id)
        project.artifacts[artifact.key] = artifact
        step_value = str(artifact.metadata.get("step") or project.current_step.value)
        try:
            project.touch(WorkflowStep(step_value))
        except ValueError:
            project.touch()
        affected = self._mark_descendants_stale(project, artifact)
        return self.save(project), affected

    def delete(self, project_id: str) -> NovelProject:
        project = self.repository.delete(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def remove_artifact(self, project_id: str, artifact_key: str) -> tuple[NovelProject, list[str]]:
        project = self.get(project_id)
        removed: list[str] = []

        target = project.artifacts.get(artifact_key)
        if target is None:
            raise LookupError(f"artifact not found: {project_id}/{artifact_key}")

        step_key = _artifact_step_key(target)
        scope_payload = {
            "scope_kind": target.metadata.get("scope_kind", "project"),
            "volume_index": target.metadata.get("volume_index"),
            "chapter_index": target.metadata.get("chapter_index"),
        }

        for candidate_key, candidate in list(project.artifacts.items()):
            if candidate.key == target.key or _artifact_matches_descendant_scope(candidate, step_key, scope_payload):
                if project.remove_artifact(candidate_key) is not None:
                    removed.append(candidate_key)

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
