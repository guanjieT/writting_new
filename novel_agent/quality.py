from __future__ import annotations

from typing import Any

from .domain import Artifact, NovelProject


def _active_artifacts(project: NovelProject) -> list[Artifact]:
    return [
        artifact
        for artifact in project.artifacts.values()
        if not artifact.metadata.get("stale") and artifact.metadata.get("state") != "stale"
    ]


def _scoped_key(artifact: Artifact) -> tuple[int, int] | None:
    metadata = artifact.metadata or {}
    try:
        volume_index = int(metadata.get("volume_index") or 0)
        chapter_index = int(metadata.get("chapter_index") or 0)
    except (TypeError, ValueError):
        return None
    if volume_index <= 0 or chapter_index <= 0:
        return None
    return volume_index, chapter_index


def _index_by_step(project: NovelProject, step: str) -> dict[tuple[int, int], Artifact]:
    indexed: dict[tuple[int, int], Artifact] = {}
    for artifact in _active_artifacts(project):
        if artifact.metadata.get("step") != step:
            continue
        scoped_key = _scoped_key(artifact)
        if scoped_key is None:
            continue
        indexed[scoped_key] = artifact
    return indexed


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
    plans = _index_by_step(project, "chapter_plan")
    chapters = _index_by_step(project, "chapter")
    revisions = _index_by_step(project, "revision")
    consistency = _index_by_step(project, "consistency")
    memories = _index_by_step(project, "memory")
    keys = sorted(set(plans) | set(chapters) | set(revisions) | set(consistency) | set(memories))
    items: list[dict[str, Any]] = []
    blocking_issue_count = 0

    for volume_index, chapter_index in keys:
        plan = plans.get((volume_index, chapter_index))
        chapter = chapters.get((volume_index, chapter_index))
        target_words = _target_words(plan, chapter)
        actual_words = len((chapter.content if chapter else "").strip())
        issues: list[str] = []

        if plan is None:
            issues.append("missing_chapter_plan")
        if chapter is None:
            issues.append("missing_chapter")
        if chapter is not None and target_words and actual_words < target_words:
            issues.append("chapter_too_short")
        if (volume_index, chapter_index) not in consistency:
            issues.append("missing_consistency")
        if (volume_index, chapter_index) not in memories:
            issues.append("missing_memory")

        blocking = any(issue in issues for issue in ("missing_chapter_plan", "missing_chapter", "chapter_too_short", "missing_consistency"))
        if blocking:
            blocking_issue_count += 1
        items.append(
            {
                "volume_index": volume_index,
                "chapter_index": chapter_index,
                "target_words": target_words,
                "actual_words": actual_words,
                "has_revision": (volume_index, chapter_index) in revisions,
                "has_consistency": (volume_index, chapter_index) in consistency,
                "has_memory": (volume_index, chapter_index) in memories,
                "issues": issues,
                "blocking": blocking,
            }
        )

    return {
        "project_id": project.project_id,
        "checked_chapters": len(items),
        "blocking_issue_count": blocking_issue_count,
        "ready_for_export": bool(items) and blocking_issue_count == 0,
        "chapters": items,
    }
