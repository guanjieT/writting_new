"""Scene-level modeling helpers for long-form chapter generation.

This module does not replace the current chapter flow yet.  It provides the
stable data shape and deterministic fallback splitter needed to move from
"one prompt writes a whole chapter" toward scene-by-scene drafting.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScenePlan(BaseModel):
    scene_index: int
    title: str = ""
    summary: str = ""
    location: str = ""
    pov_character: str = ""
    purpose: str = ""
    conflict: str = ""
    emotional_shift: str = ""
    information_delta: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    target_words: int = 0


class ChapterScenePlan(BaseModel):
    volume_index: int
    chapter_index: int
    chapter_title: str = ""
    scenes: list[ScenePlan] = Field(default_factory=list)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def build_scene_plan_from_chapter_structured(structured: dict[str, Any]) -> ChapterScenePlan:
    """Create a scene plan from a chapter_plan structured payload.

    If prompts already emit rich scene objects, they are preserved.  If they only
    emit strings, we convert each string into a scene shell so downstream code
    can address scenes individually.
    """
    volume_index = max(_safe_int(structured.get("volume_index"), 1), 1)
    chapter_index = max(_safe_int(structured.get("chapter_index"), 1), 1)
    chapter_title = str(structured.get("title") or "")
    total_target_words = max(_safe_int(structured.get("target_words"), 0), 0)
    raw_scenes = structured.get("scene_summaries") or []
    if not isinstance(raw_scenes, list):
        raw_scenes = [raw_scenes]
    if not raw_scenes:
        raw_scenes = [structured.get("summary") or structured.get("main_event") or chapter_title or "本章核心场景"]

    per_scene_words = total_target_words // max(len(raw_scenes), 1) if total_target_words else 0
    scenes: list[ScenePlan] = []
    for index, item in enumerate(raw_scenes, start=1):
        if isinstance(item, dict):
            scene = ScenePlan(
                scene_index=max(_safe_int(item.get("scene_index"), index), index),
                title=str(item.get("title") or f"场景 {index}"),
                summary=str(item.get("summary") or item.get("content") or ""),
                location=str(item.get("location") or ""),
                pov_character=str(item.get("pov_character") or structured.get("pov_character") or ""),
                purpose=str(item.get("purpose") or item.get("goal") or ""),
                conflict=str(item.get("conflict") or structured.get("conflict") or ""),
                emotional_shift=str(item.get("emotional_shift") or ""),
                information_delta=[str(x) for x in item.get("information_delta", [])] if isinstance(item.get("information_delta"), list) else [],
                characters=[str(x) for x in item.get("characters", [])] if isinstance(item.get("characters"), list) else [str(x) for x in structured.get("characters", [])] if isinstance(structured.get("characters"), list) else [],
                target_words=max(_safe_int(item.get("target_words"), per_scene_words), 0),
            )
        else:
            scene = ScenePlan(
                scene_index=index,
                title=f"场景 {index}",
                summary=str(item or ""),
                pov_character=str(structured.get("pov_character") or ""),
                conflict=str(structured.get("conflict") or ""),
                characters=[str(x) for x in structured.get("characters", [])] if isinstance(structured.get("characters"), list) else [],
                target_words=per_scene_words,
            )
        scenes.append(scene)

    return ChapterScenePlan(
        volume_index=volume_index,
        chapter_index=chapter_index,
        chapter_title=chapter_title,
        scenes=scenes,
    )


def scene_plan_payload(structured: dict[str, Any]) -> dict[str, Any]:
    return build_scene_plan_from_chapter_structured(structured).model_dump(mode="json")
