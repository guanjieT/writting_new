from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class WorkflowStep(str, Enum):
    CREATED = "created"
    REQUIREMENTS = "requirements"
    STORY_BIBLE = "story_bible"
    CHARACTERS = "characters"
    OUTLINE = "outline"
    ROUGH_VOLUME_OUTLINE = "rough_volume_outline"
    VOLUME_OUTLINE = "volume_outline"
    ROUGH_CHAPTER_PLAN = "rough_chapter_plan"
    CHAPTER_PLAN = "chapter_plan"
    CHAPTER = "chapter"
    REVISION = "revision"
    CONSISTENCY = "consistency"
    MEMORY = "memory"
    COMPLETE = "complete"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectInput(BaseModel):
    title: str
    genre: str
    premise: str = ""
    target_words: int = 80_000
    target_volume_count: int = 1
    target_chapters_per_volume: int = 12
    target_audience: str = ""
    tone: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    outline_focus: list[str] = Field(default_factory=list)
    core_requirements: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)


class ArtifactSummary(BaseModel):
    summary: str = ""
    overview: str = ""
    key_facts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    best_for_steps: list[str] = Field(default_factory=list)
    best_for_reason: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)


class GeneratedArtifactPayload(BaseModel):
    content: str = ""
    overview: str = ""
    key_facts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    best_for_reason: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_content_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        content = value.get("content")
        if isinstance(content, (dict, list)):
            value["content"] = json_dumps(content)
        structured: dict[str, Any] = {}
        raw_structured = value.get("structured")
        if isinstance(raw_structured, dict):
            structured.update(raw_structured)
        elif isinstance(raw_structured, list):
            structured["items"] = raw_structured
        elif raw_structured not in (None, ""):
            structured["value"] = raw_structured

        fixed_keys = {"content", "overview", "key_facts", "constraints", "open_questions", "best_for_reason", "structured"}
        for key in list(value.keys()):
            if key in fixed_keys:
                continue
            structured[key] = value.pop(key)

        if structured:
            value["structured"] = structured
        elif "structured" in value and value["structured"] in (None, "", {}, []):
            value.pop("structured", None)
        return value


def json_dumps(value: Any) -> str:
    from json import dumps

    return dumps(value, ensure_ascii=False, indent=2)


class Artifact(BaseModel):
    key: str
    title: str
    content: str
    summary: ArtifactSummary = Field(default_factory=ArtifactSummary)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeItem(BaseModel):
    item_id: str = Field(default_factory=lambda: new_id("know"))
    source_artifact_key: str
    source_step: str = ""
    kind: str
    text: str
    scope_kind: str = "project"
    volume_index: int | None = None
    chapter_index: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class NovelProject(BaseModel):
    project_id: str = Field(default_factory=lambda: new_id("proj"))
    input: ProjectInput
    current_step: WorkflowStep = WorkflowStep.CREATED
    status: WorkflowStep = WorkflowStep.CREATED
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    artifact_history: dict[str, list[Artifact]] = Field(default_factory=dict)
    knowledge_base: list[KnowledgeItem] = Field(default_factory=list)
    structured_memory: dict[str, list[dict[str, Any]]] = Field(
        default_factory=lambda: {
            "characters": [],
            "locations": [],
            "items": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
            "relationships": [],
            "world_rules": [],
        }
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self, step: WorkflowStep | None = None) -> None:
        if step is not None:
            self.current_step = step
            self.status = step
        self.updated_at = utc_now()

    def remove_artifact(self, key: str) -> Artifact | None:
        return self.artifacts.pop(key, None)

    def summary(self) -> str:
        artifact_names = ", ".join(self.artifacts.keys()) or "none"
        return f"{self.input.title} ({self.input.genre}) -> {artifact_names}"


class AgentContext(BaseModel):
    project_id: str
    temperature: float = 0.7
    max_tokens: int = 1200
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    step: WorkflowStep
    artifact: Artifact
    notes: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    project_id: str
    task_name: str
    scope_kind: str = "project"
    volume_index: int | None = None
    chapter_index: int | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("audit"))
    action: str
    project_id: str | None = None
    actor: str = "system"
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProjectNotFoundError(RuntimeError):
    pass


class TaskNotFoundError(RuntimeError):
    pass


class UnsupportedStepError(RuntimeError):
    pass


class WorkflowOrderError(RuntimeError):
    pass


@runtime_checkable
class ProjectRepository(Protocol):
    def list(self) -> list[NovelProject]:
        raise NotImplementedError

    def get(self, project_id: str) -> NovelProject | None:
        raise NotImplementedError

    def save(self, project: NovelProject) -> NovelProject:
        raise NotImplementedError

    def delete(self, project_id: str) -> NovelProject | None:
        raise NotImplementedError


@runtime_checkable
class PromptStore(Protocol):
    def load(self, template_name: str) -> str:
        raise NotImplementedError


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1200,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError


@runtime_checkable
class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None:
        raise NotImplementedError


@runtime_checkable
class TaskStore(Protocol):
    def create(self, task: TaskRecord) -> TaskRecord:
        raise NotImplementedError

    def get(self, task_id: str) -> TaskRecord | None:
        raise NotImplementedError

    def list(self, project_id: str | None = None) -> list[TaskRecord]:
        raise NotImplementedError

    def update(self, task: TaskRecord) -> TaskRecord:
        raise NotImplementedError

    def delete(self, task_id: str) -> None:
        raise NotImplementedError

    def delete_by_project(self, project_id: str) -> int:
        raise NotImplementedError
