from __future__ import annotations

from typing import Any

from .domain import Artifact, NovelProject
from .validators import index_by_step, issue_counts, validate_project


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


def build_quality_report(project: NovelProject) -> dict[str, Any]:
    plans = index_by_step(project, "chapter_plan")
    chapters = index_by_step(project, "chapter")
    revisions = index_by_step(project, "revision")
    consistency = index_by_step(project, "consistency")
    memories = index_by_step(project, "memory")
    keys = sorted(set(plans) | set(chapters) | set(revisions) | set(consistency) | set(memories))
    items: list[dict[str, Any]] = []

    validator_issues = validate_project(project)
    issues_by_chapter: dict[tuple[int, int], list[dict[str, Any]]] = {}
    project_level_issues: list[dict[str, Any]] = []
    for issue in validator_issues:
        issue_dict = issue.to_dict()
        if issue.volume_index and issue.chapter_index:
            issues_by_chapter.setdefault((issue.volume_index, issue.chapter_index), []).append(issue_dict)
        else:
            project_level_issues.append(issue_dict)

    for volume_index, chapter_index in keys:
        plan = plans.get((volume_index, chapter_index))
        chapter = chapters.get((volume_index, chapter_index))
        target_words = _target_words(plan, chapter)
        actual_words = len((chapter.content if chapter else "").strip())
        chapter_issues = issues_by_chapter.get((volume_index, chapter_index), [])
        blocking = any(issue.get("severity") == "blocking" for issue in chapter_issues)
        items.append(
            {
                "volume_index": volume_index,
                "chapter_index": chapter_index,
                "target_words": target_words,
                "actual_words": actual_words,
                "has_revision": (volume_index, chapter_index) in revisions,
                "has_consistency": (volume_index, chapter_index) in consistency,
                "has_memory": (volume_index, chapter_index) in memories,
                "issues": [issue.get("type") for issue in chapter_issues],
                "detailed_issues": chapter_issues,
                "blocking": blocking,
            }
        )

    counts = issue_counts(validator_issues)
    return {
        "project_id": project.project_id,
        "checked_chapters": len(items),
        "blocking_issue_count": counts.get("blocking", 0),
        "warning_issue_count": counts.get("warning", 0),
        "info_issue_count": counts.get("info", 0),
        "ready_for_export": bool(items) and counts.get("blocking", 0) == 0,
        "project_level_issues": project_level_issues,
        "chapters": items,
        "validator_issues": [issue.to_dict() for issue in validator_issues],
    }
