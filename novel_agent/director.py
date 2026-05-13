"""Director/controller helpers for long-form generation.

This is the first layer of agent autonomy: it inspects project state and quality
issues, then proposes a deterministic repair/generation queue.  Existing UI/API
can use this plan without changing the core orchestrator contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain import NovelProject
from .quality import build_quality_report
from .workflow_spec import WORKFLOW_STEPS


@dataclass(frozen=True)
class DirectorAction:
    action: str
    step: str
    reason: str
    priority: int = 100
    volume_index: int | None = None
    chapter_index: int | None = None
    payload_hint: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "step": self.step,
            "reason": self.reason,
            "priority": self.priority,
            "volume_index": self.volume_index,
            "chapter_index": self.chapter_index,
            "payload_hint": self.payload_hint or {},
        }


def _has_project_artifact(project: NovelProject, step: str) -> bool:
    return any(
        artifact.metadata.get("step") == step
        and artifact.metadata.get("scope_kind", "project") == "project"
        and not artifact.metadata.get("stale")
        for artifact in project.artifacts.values()
    )


def _has_scoped_artifact(project: NovelProject, step: str, volume_index: int, chapter_index: int | None = None) -> bool:
    for artifact in project.artifacts.values():
        metadata = artifact.metadata or {}
        if metadata.get("step") != step or metadata.get("stale"):
            continue
        if int(metadata.get("volume_index") or 0) != volume_index:
            continue
        if chapter_index is not None and int(metadata.get("chapter_index") or 0) != chapter_index:
            continue
        return True
    return False


def build_generation_plan(project: NovelProject) -> list[DirectorAction]:
    """Build the next sensible generation actions for an incomplete project."""
    actions: list[DirectorAction] = []

    for rank, step in enumerate(WORKFLOW_STEPS, start=1):
        if step.scope != "project":
            continue
        if not _has_project_artifact(project, step.key):
            actions.append(DirectorAction("generate", step.key, f"缺少项目级步骤：{step.label}", priority=rank * 10))
            return sorted(actions, key=lambda item: item.priority)

    target_volumes = max(int(project.input.target_volume_count or 1), 1)
    target_chapters = max(int(project.input.target_chapters_per_volume or 1), 1)

    for volume_index in range(1, target_volumes + 1):
        if not _has_scoped_artifact(project, "volume_outline", volume_index):
            actions.append(DirectorAction("generate", "volume_outline", f"第 {volume_index} 卷缺少完整卷纲。", 100, volume_index, payload_hint={"volume_index": volume_index}))
            return actions
        if not _has_scoped_artifact(project, "rough_chapter_plan", volume_index):
            actions.append(DirectorAction("generate", "rough_chapter_plan", f"第 {volume_index} 卷缺少粗章纲。", 110, volume_index, payload_hint={"volume_index": volume_index, "target_chapter_count": target_chapters}))
            return actions
        for chapter_index in range(1, target_chapters + 1):
            if not _has_scoped_artifact(project, "chapter_plan", volume_index, chapter_index):
                actions.append(DirectorAction("generate", "chapter_plan", f"第 {volume_index} 卷第 {chapter_index} 章缺少章节计划。", 200, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
                return actions
            if not _has_scoped_artifact(project, "chapter", volume_index, chapter_index):
                actions.append(DirectorAction("generate", "chapter", f"第 {volume_index} 卷第 {chapter_index} 章缺少正文。", 210, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
                return actions
    return actions


def build_repair_plan(project: NovelProject) -> list[DirectorAction]:
    """Build a repair queue from the enhanced quality report."""
    report = build_quality_report(project)
    actions: list[DirectorAction] = []
    for issue in report.get("validator_issues", []):
        issue_type = issue.get("type")
        volume_index = issue.get("volume_index")
        chapter_index = issue.get("chapter_index")
        if issue_type == "missing_chapter_plan":
            actions.append(DirectorAction("generate", "chapter_plan", issue.get("message", "缺少章节计划"), 10, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
        elif issue_type in {"missing_chapter", "chapter_too_short"}:
            actions.append(DirectorAction("generate", "chapter", issue.get("message", "章节正文需要生成或扩写"), 20, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
        elif issue_type == "missing_consistency":
            actions.append(DirectorAction("validate", "consistency", issue.get("message", "缺少一致性检查"), 30, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
        elif issue_type == "missing_memory":
            actions.append(DirectorAction("update_memory", "memory", issue.get("message", "缺少记忆整理"), 40, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index}))
        elif issue_type in {"weak_scene_breakdown", "empty_scene_summary"}:
            actions.append(DirectorAction("revise_plan", "chapter_plan", issue.get("message", "章节计划需要场景级补强"), 50, volume_index, chapter_index, {"volume_index": volume_index, "chapter_index": chapter_index, "focus": "scene_breakdown"}))
        elif issue_type in {"missing_character_memory", "missing_world_rule_memory", "missing_timeline_memory", "too_many_open_foreshadowing"}:
            actions.append(DirectorAction("update_memory", "memory", issue.get("message", "长期记忆需要补强"), 60, volume_index, chapter_index, {"focus": issue_type}))

    if not actions:
        actions.extend(build_generation_plan(project))
    deduped: dict[tuple[str, str, int | None, int | None], DirectorAction] = {}
    for action in actions:
        key = (action.action, action.step, action.volume_index, action.chapter_index)
        if key not in deduped or action.priority < deduped[key].priority:
            deduped[key] = action
    return sorted(deduped.values(), key=lambda item: item.priority)


def director_snapshot(project: NovelProject) -> dict[str, Any]:
    repair_plan = build_repair_plan(project)
    return {
        "project_id": project.project_id,
        "next_actions": [action.to_dict() for action in repair_plan[:20]],
        "has_blocking_repairs": any(action.action in {"generate", "validate", "revise_plan"} for action in repair_plan),
    }
