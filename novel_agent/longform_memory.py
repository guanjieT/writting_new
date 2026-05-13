"""Structured long-form memory helpers.

The previous project memory was mostly a flat list of extracted facts.  That is
useful, but a long novel needs durable entities: characters, locations, items,
plot threads, foreshadowing, timeline events, relationships and world rules.

This module extracts conservative structured memory records from generated
artifacts.  It is intentionally heuristic and model-agnostic: prompts can later
emit richer structured fields and these helpers will preserve them without
forcing a database migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .domain import Artifact, NovelProject

MEMORY_BUCKETS = (
    "characters",
    "locations",
    "items",
    "plot_threads",
    "foreshadowing",
    "timeline_events",
    "relationships",
    "world_rules",
)


def empty_structured_memory() -> dict[str, list[dict[str, Any]]]:
    return {bucket: [] for bucket in MEMORY_BUCKETS}


def normalize_structured_memory(value: Any) -> dict[str, list[dict[str, Any]]]:
    memory = empty_structured_memory()
    if not isinstance(value, Mapping):
        return memory
    for bucket in MEMORY_BUCKETS:
        raw_items = value.get(bucket, [])
        if isinstance(raw_items, list):
            memory[bucket] = [dict(item) for item in raw_items if isinstance(item, Mapping)]
    return memory


def _artifact_scope(artifact: Artifact) -> dict[str, Any]:
    metadata = artifact.metadata or {}
    scope = {
        "source_artifact_key": artifact.key,
        "source_step": metadata.get("step", ""),
        "scope_kind": metadata.get("scope_kind", "project"),
    }
    if metadata.get("volume_index") not in (None, ""):
        scope["volume_index"] = int(metadata.get("volume_index") or 0)
    if metadata.get("chapter_index") not in (None, ""):
        scope["chapter_index"] = int(metadata.get("chapter_index") or 0)
    return scope


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(records: list[dict[str, Any]], record: dict[str, Any], identity_keys: tuple[str, ...]) -> None:
    identity = tuple(_text(record.get(key)).lower() for key in identity_keys)
    if not any(tuple(_text(existing.get(key)).lower() for key in identity_keys) == identity for existing in records):
        records.append(record)


def _extract_character_records(structured: Mapping[str, Any], artifact: Artifact) -> list[dict[str, Any]]:
    scope = _artifact_scope(artifact)
    records: list[dict[str, Any]] = []

    raw_characters = structured.get("characters")
    if isinstance(raw_characters, list):
        for item in raw_characters:
            if isinstance(item, Mapping):
                name = _text(item.get("name") or item.get("character") or item.get("title"))
                if name:
                    records.append({"name": name, "state": dict(item), **scope})
            else:
                name = _text(item)
                if name:
                    records.append({"name": name, "state": {}, **scope})

    raw_intro = structured.get("introduced_characters")
    if isinstance(raw_intro, list):
        for item in raw_intro:
            name = _text(item.get("name") if isinstance(item, Mapping) else item)
            if name:
                records.append({"name": name, "first_seen": True, "state": dict(item) if isinstance(item, Mapping) else {}, **scope})

    return records


def _extract_world_rule_records(structured: Mapping[str, Any], artifact: Artifact) -> list[dict[str, Any]]:
    scope = _artifact_scope(artifact)
    records: list[dict[str, Any]] = []
    for key in ("world_rules", "constraints", "rules"):
        raw = structured.get(key)
        if isinstance(raw, list):
            for item in raw:
                text = _text(item.get("text") if isinstance(item, Mapping) else item)
                if text:
                    records.append({"rule": text, "kind": key, **scope})
    for text in artifact.summary.constraints:
        clean = _text(text)
        if clean:
            records.append({"rule": clean, "kind": "artifact_constraint", **scope})
    return records


def _extract_plot_threads(structured: Mapping[str, Any], artifact: Artifact) -> list[dict[str, Any]]:
    scope = _artifact_scope(artifact)
    records: list[dict[str, Any]] = []
    for key in ("story_arcs", "global_goals", "main_conflicts", "arc_segments"):
        raw = structured.get(key)
        if not isinstance(raw, list):
            continue
        for index, item in enumerate(raw, start=1):
            if isinstance(item, Mapping):
                title = _text(item.get("title") or item.get("goal") or item.get("summary") or item.get("conflict"))
                summary = _text(item.get("summary") or item.get("hint") or item.get("description"))
                payload = dict(item)
            else:
                title = _text(item)
                summary = title
                payload = {"text": title}
            if title:
                records.append({"thread_id": f"{artifact.key}:{key}:{index}", "title": title, "summary": summary, "kind": key, "state": payload, **scope})
    return records


def _extract_timeline_events(structured: Mapping[str, Any], artifact: Artifact) -> list[dict[str, Any]]:
    scope = _artifact_scope(artifact)
    records: list[dict[str, Any]] = []
    for key in ("main_event", "scene_summaries", "chapters"):
        raw = structured.get(key)
        if isinstance(raw, str) and raw.strip():
            records.append({"event": raw.strip(), "kind": key, **scope})
        elif isinstance(raw, list):
            for index, item in enumerate(raw, start=1):
                if isinstance(item, Mapping):
                    event = _text(item.get("main_event") or item.get("summary") or item.get("event") or item.get("title"))
                    payload = dict(item)
                else:
                    event = _text(item)
                    payload = {"text": event}
                if event:
                    records.append({"event": event, "sequence": index, "kind": key, "state": payload, **scope})
    return records


def _extract_foreshadowing(structured: Mapping[str, Any], artifact: Artifact) -> list[dict[str, Any]]:
    scope = _artifact_scope(artifact)
    records: list[dict[str, Any]] = []
    for key in ("hook", "ending_hook", "open_questions"):
        raw = structured.get(key)
        if isinstance(raw, str) and raw.strip():
            records.append({"cue": raw.strip(), "status": "open", "kind": key, **scope})
        elif isinstance(raw, list):
            for item in raw:
                cue = _text(item.get("cue") if isinstance(item, Mapping) else item)
                if cue:
                    records.append({"cue": cue, "status": "open", "kind": key, **scope})
    for question in artifact.summary.open_questions:
        cue = _text(question)
        if cue:
            records.append({"cue": cue, "status": "open", "kind": "artifact_open_question", **scope})
    return records


def extract_structured_memory(artifact: Artifact) -> dict[str, list[dict[str, Any]]]:
    structured = artifact.summary.structured if isinstance(artifact.summary.structured, Mapping) else {}
    memory = empty_structured_memory()
    memory["characters"].extend(_extract_character_records(structured, artifact))
    memory["world_rules"].extend(_extract_world_rule_records(structured, artifact))
    memory["plot_threads"].extend(_extract_plot_threads(structured, artifact))
    memory["timeline_events"].extend(_extract_timeline_events(structured, artifact))
    memory["foreshadowing"].extend(_extract_foreshadowing(structured, artifact))
    return memory


def merge_structured_memory(project: NovelProject, artifact: Artifact) -> int:
    """Merge extracted memory into the project and return inserted count."""
    if not hasattr(project, "structured_memory") or project.structured_memory is None:
        project.structured_memory = empty_structured_memory()  # type: ignore[attr-defined]
    project.structured_memory = normalize_structured_memory(project.structured_memory)

    extracted = extract_structured_memory(artifact)
    inserted = 0
    identities = {
        "characters": ("name",),
        "locations": ("name",),
        "items": ("name",),
        "plot_threads": ("thread_id",),
        "foreshadowing": ("cue", "source_artifact_key"),
        "timeline_events": ("event", "source_artifact_key"),
        "relationships": ("source", "target", "relation"),
        "world_rules": ("rule",),
    }
    for bucket, records in extracted.items():
        target = project.structured_memory.setdefault(bucket, [])
        before = len(target)
        for record in records:
            _append_unique(target, record, identities[bucket])
        inserted += len(target) - before
    return inserted


def relevant_structured_memory(project: NovelProject, *, volume_index: int = 0, chapter_index: int = 0, limit_per_bucket: int = 30) -> dict[str, list[dict[str, Any]]]:
    """Return memory scoped for a generation request.

    Project-level records always qualify.  Volume-level records must match the
    current volume.  Chapter-level records from future chapters are excluded.
    """
    memory = normalize_structured_memory(getattr(project, "structured_memory", {}))
    result = empty_structured_memory()
    for bucket, records in memory.items():
        selected: list[dict[str, Any]] = []
        for record in reversed(records):
            scope_kind = record.get("scope_kind", "project")
            rec_volume = int(record.get("volume_index") or 0)
            rec_chapter = int(record.get("chapter_index") or 0)
            if scope_kind == "volume" and volume_index and rec_volume != volume_index:
                continue
            if scope_kind == "chapter":
                if volume_index and rec_volume != volume_index:
                    continue
                if chapter_index and rec_chapter > chapter_index:
                    continue
            selected.append(record)
            if len(selected) >= limit_per_bucket:
                break
        result[bucket] = list(reversed(selected))
    return result
