"""Deterministic validators for long-form novel artifacts.

These validators do not try to replace LLM review.  They catch structural and
process-level failures that should be blocked before export: missing plans,
short chapters, missing scene breakdowns, absent consistency/memory passes,
unresolved foreshadowing and weak structured memory coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain import Artifact, NovelProject
from .longform_memory import normalize_structured_memory
from .scene_model import build_scene_plan_from_chapter_structured


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    issue_type: str
    message: str
    volume_index: int | None = None
    chapter_index: int | None = None
    artifact_key: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "type": self.issue_type,
            "message": self.message,
            "volume_index": self.volume_index,
            "chapter_index": self.chapter_index,
            "artifact_key": self.artifact_key,
            "suggested_fix": self.suggested_fix,
        }


def active_artifacts(project: NovelProject) -> list[Artifact]:
    return [a for a in project.artifacts.values() if not a.metadata.get("stale") and a.metadata.get("state") != "stale"]


def scoped_key(artifact: Artifact) -> tuple[int, int] | None:
    metadata = artifact.metadata or {}
    try:
        volume_index = int(metadata.get("volume_index") or 0)
        chapter_index = int(metadata.get("chapter_index") or 0)
    except (TypeError, ValueError):
        return None
    if volume_index <= 0 or chapter_index <= 0:
        return None
    return volume_index, chapter_index


def index_by_step(project: NovelProject, step: str) -> dict[tuple[int, int], Artifact]:
    result: dict[tuple[int, int], Artifact] = {}
    for artifact in active_artifacts(project):
        if artifact.metadata.get("step") != step:
            continue
        key = scoped_key(artifact)
        if key is not None:
            result[key] = artifact
    return result


def _target_words(plan: Artifact | None, chapter: Artifact | None) -> int:
    for artifact in (plan, chapter):
        if artifact is None:
            continue
        structured = artifact.summary.structured if isinstance(artifact.summary.structured, dict) else {}
        for key in ("min_words", "target_words"):
            try:
                value = int(structured.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    return 0


def validate_chapter_completeness(project: NovelProject) -> list[ValidationIssue]:
    plans = index_by_step(project, "chapter_plan")
    chapters = index_by_step(project, "chapter")
    revisions = index_by_step(project, "revision")
    consistency = index_by_step(project, "consistency")
    memories = index_by_step(project, "memory")
    keys = sorted(set(plans) | set(chapters) | set(revisions) | set(consistency) | set(memories))
    issues: list[ValidationIssue] = []
    for volume_index, chapter_index in keys:
        plan = plans.get((volume_index, chapter_index))
        chapter = chapters.get((volume_index, chapter_index))
        target_words = _target_words(plan, chapter)
        actual_words = len((chapter.content if chapter else "").strip())
        if plan is None:
            issues.append(ValidationIssue("blocking", "missing_chapter_plan", "缺少章节计划。", volume_index, chapter_index, suggested_fix="先生成完整章节计划。"))
        if chapter is None:
            issues.append(ValidationIssue("blocking", "missing_chapter", "缺少章节正文。", volume_index, chapter_index, suggested_fix="生成章节正文。"))
        if chapter is not None and target_words and actual_words < target_words:
            issues.append(ValidationIssue("blocking", "chapter_too_short", f"章节正文长度不足：目标至少 {target_words}，实际 {actual_words}。", volume_index, chapter_index, chapter.key, "提高 max_tokens 后重写或扩写本章。"))
        if (volume_index, chapter_index) not in consistency:
            issues.append(ValidationIssue("blocking", "missing_consistency", "缺少一致性检查。", volume_index, chapter_index, suggested_fix="运行一致性检查。"))
        if (volume_index, chapter_index) not in memories:
            issues.append(ValidationIssue("warning", "missing_memory", "缺少记忆整理。", volume_index, chapter_index, suggested_fix="运行记忆整理以更新长期记忆。"))
        if (volume_index, chapter_index) not in revisions:
            issues.append(ValidationIssue("info", "missing_revision", "尚未生成修订版本。", volume_index, chapter_index, suggested_fix="如正文质量不稳定，运行修订。"))
    return issues


def validate_scene_breakdown(project: NovelProject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key, plan in index_by_step(project, "chapter_plan").items():
        structured = plan.summary.structured if isinstance(plan.summary.structured, dict) else {}
        scene_plan = build_scene_plan_from_chapter_structured(structured)
        if len(scene_plan.scenes) < 2:
            issues.append(ValidationIssue("warning", "weak_scene_breakdown", "章节计划场景拆分不足，可能导致正文像大纲扩写。", key[0], key[1], plan.key, "补充 2-5 个 scene_summaries，或启用场景级生成。"))
        for scene in scene_plan.scenes:
            if not scene.summary:
                issues.append(ValidationIssue("warning", "empty_scene_summary", f"场景 {scene.scene_index} 缺少摘要。", key[0], key[1], plan.key, "补全场景摘要。"))
            if not scene.conflict:
                issues.append(ValidationIssue("info", "scene_without_conflict", f"场景 {scene.scene_index} 缺少明确冲突。", key[0], key[1], plan.key, "补充场景冲突或阻力。"))
    return issues


def validate_memory_coverage(project: NovelProject) -> list[ValidationIssue]:
    memory = normalize_structured_memory(getattr(project, "structured_memory", {}))
    issues: list[ValidationIssue] = []
    if not memory["characters"]:
        issues.append(ValidationIssue("warning", "missing_character_memory", "结构化角色记忆为空。", suggested_fix="让角色框架、章节计划或记忆整理输出 characters / introduced_characters。"))
    if not memory["world_rules"]:
        issues.append(ValidationIssue("warning", "missing_world_rule_memory", "结构化世界规则记忆为空。", suggested_fix="让世界观或一致性步骤输出 world_rules / constraints。"))
    if not memory["timeline_events"]:
        issues.append(ValidationIssue("warning", "missing_timeline_memory", "结构化时间线为空。", suggested_fix="章节计划和正文生成后运行记忆整理。"))
    return issues


def validate_foreshadowing(project: NovelProject) -> list[ValidationIssue]:
    memory = normalize_structured_memory(getattr(project, "structured_memory", {}))
    open_items = [item for item in memory["foreshadowing"] if str(item.get("status", "open")) == "open"]
    issues: list[ValidationIssue] = []
    if len(open_items) > 20:
        issues.append(ValidationIssue("warning", "too_many_open_foreshadowing", f"未回收伏笔/开放问题数量较多：{len(open_items)}。", suggested_fix="在卷纲或章节计划中安排回收点。"))
    return issues


def validate_project(project: NovelProject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(validate_chapter_completeness(project))
    issues.extend(validate_scene_breakdown(project))
    issues.extend(validate_memory_coverage(project))
    issues.extend(validate_foreshadowing(project))
    return issues


def issue_counts(issues: list[ValidationIssue]) -> dict[str, int]:
    counts = {"blocking": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts
