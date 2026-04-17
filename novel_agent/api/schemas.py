from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..domain import Artifact, NovelProject, ProjectInput, TaskRecord


class ProjectCreateRequest(ProjectInput):
    pass


class FieldCompletionRequest(BaseModel):
    step: str
    step_label: str = ""
    step_description: str = ""
    field_key: str
    field_label: str
    field_type: str = "text"
    field_placeholder: str = ""
    current_value: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7
    max_tokens: int = 700


class FieldCompletionResponse(BaseModel):
    step: str
    field_key: str
    suggestion: str


class GenerationBaseRequest(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 1200


class RequirementsRequest(GenerationBaseRequest):
    requirements_text: str = ""
    audience: str = ""
    notes: list[str] = Field(default_factory=list)


class StoryBibleRequest(GenerationBaseRequest):
    theme: str = ""
    world_rules: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CharacterRequest(GenerationBaseRequest):
    role_capacity: int = 4
    core_roles: list[str] = Field(default_factory=list)
    role_slots: list[str] = Field(default_factory=list)
    role_rules: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OutlineRequest(GenerationBaseRequest):
    volume_count: int = 1
    chapters_per_volume: int = 12
    focus_points: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VolumeOutlineRequest(GenerationBaseRequest):
    volume_index: int = 1
    volume_title: str = ""
    volume_summary: str = ""
    volume_goal: str = ""
    volume_conflict: str = ""
    volume_hook: str = ""
    chapter_briefs: list[str] = Field(default_factory=list)
    target_words: int = 0
    target_chapter_count: int = 0
    confirmed: bool = False
    notes: list[str] = Field(default_factory=list)


class ChapterPlanRequest(GenerationBaseRequest):
    volume_index: int = 1
    chapter_index: int = 1
    chapter_title: str = ""
    chapter_summary: str = ""
    chapter_type: str = "主线推进章"
    pov_character: str = ""
    protagonist_present: bool = True
    conflict: str = ""
    hook: str = ""
    target_words: int = 3000
    min_words: int = 2000
    characters: list[str] = Field(default_factory=list)
    introduced_characters: list[str] = Field(default_factory=list)
    scene_summaries: list[str] = Field(default_factory=list)
    confirmed: bool = False
    plan_notes: str = ""
    notes: list[str] = Field(default_factory=list)


class ChapterRequest(GenerationBaseRequest):
    volume_index: int = 1
    chapter_index: int = 1
    chapter_goal: str = ""
    target_words: int = 2000
    scene_beats: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RevisionRequest(GenerationBaseRequest):
    target_artifact: str = ""
    instruction: str = ""
    focus_areas: list[str] = Field(default_factory=list)


class ConsistencyRequest(GenerationBaseRequest):
    scope: str = "project"
    known_rules: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MemoryRequest(GenerationBaseRequest):
    query: str = ""
    top_k: int = 5
    notes: list[str] = Field(default_factory=list)


ProjectResponse = NovelProject
TaskResponse = TaskRecord
ArtifactResponse = Artifact


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
