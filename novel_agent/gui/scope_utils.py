"""Scope utilities — Python port of scope-utils.js + planning-defaults.js + structured-parsers.js + artifact-selectors.js."""

from __future__ import annotations

import re
from typing import Any

from .step_fields import FALLBACK_WORKFLOW_STEPS, get_step_label

# ---------------------------------------------------------------------------
# Scope kind mapping (from scope-utils.js)
# ---------------------------------------------------------------------------

STEP_SCOPE_KIND: dict[str, str] = {
    "outline": "project",
    "rough_volume_outline": "project",
    "volume_outline": "volume",
    "rough_chapter_plan": "volume",
    "chapter_plan": "chapter",
    "chapter": "chapter",
    "revision": "chapter",
    "consistency": "chapter",
    "memory": "chapter",
}


def get_step_scope_kind(step: str) -> str:
    return STEP_SCOPE_KIND.get(step, "project")


def normalize_scope_selection(selection: dict | None = None, payload: dict | None = None) -> dict:
    s = selection or {}
    p = payload or {}

    def _int(key: str, fallback: int = 1) -> int:
        for src in (s, p):
            v = src.get(key)
            if v is not None:
                try:
                    iv = int(v)
                    if iv > 0:
                        return iv
                except (ValueError, TypeError):
                    pass
        return fallback

    return {"volume_index": _int("volume_index"), "chapter_index": _int("chapter_index")}


def selection_for_step(step: str, selection: dict | None = None) -> dict:
    scope_kind = get_step_scope_kind(step)
    if scope_kind == "project":
        return {}
    norm = normalize_scope_selection(selection)
    if scope_kind == "volume":
        return {"volume_index": norm["volume_index"]}
    return {"volume_index": norm["volume_index"], "chapter_index": norm["chapter_index"]}


# ---------------------------------------------------------------------------
# Chinese number parsing (from structured-parsers.js)
# ---------------------------------------------------------------------------

_CHINESE_NUMBERS: dict[str, int] = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def _parse_chinese_number(value: str) -> int:
    text = value.strip()
    if re.match(r"^\d+$", text):
        return int(text)
    total = 0
    current = 0
    for ch in text:
        if ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch in _CHINESE_NUMBERS:
            current = _CHINESE_NUMBERS[ch]
    return total + current


def _clean_line(value: Any) -> str:
    return re.sub(r"^[-•*\s]+", "", str(value or "")).strip()


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------

def _artifact_step_key(artifact: dict) -> str:
    meta = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
    return str(meta.get("step") or artifact.get("key", "")).split(":")[0]


def get_artifacts_for_step(snapshot: dict | None, step: str) -> list[dict]:
    artifacts = list((snapshot or {}).get("artifacts", {}).values())
    return [a for a in artifacts if _artifact_step_key(a) == step or a.get("key") == step]


def get_artifact(snapshot: dict | None, step: str) -> dict | None:
    found = get_artifacts_for_step(snapshot, step)
    return found[-1] if found else None


def get_scoped_artifact(snapshot: dict | None, step: str, selection: dict | None = None) -> dict | None:
    scope_kind = get_step_scope_kind(step)
    norm = normalize_scope_selection(selection)
    for a in get_artifacts_for_step(snapshot, step):
        meta = a.get("metadata", {}) if isinstance(a, dict) else {}
        if meta.get("scope_kind", "project") != scope_kind:
            continue
        if scope_kind == "volume":
            if meta.get("volume_index", 0) == norm["volume_index"]:
                return a
        elif scope_kind == "chapter":
            if meta.get("volume_index", 0) == norm["volume_index"] and meta.get("chapter_index", 0) == norm["chapter_index"]:
                return a
        else:
            return a
    return None


def get_artifact_for_step(snapshot: dict | None, step: str, selection: dict | None = None) -> dict | None:
    sel = selection or {}
    if sel.get("volume_index") is not None or sel.get("chapter_index") is not None:
        return get_scoped_artifact(snapshot, step, selection)
    return get_artifact(snapshot, step)


def artifact_is_stale(artifact: dict | None) -> bool:
    if not artifact:
        return False
    meta = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
    return bool(meta.get("stale") or meta.get("state") == "stale")


def _artifact_matches_selection(artifact: dict, selection: dict) -> bool:
    meta = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
    scope_kind = meta.get("scope_kind", "project")
    if scope_kind == "project":
        return True
    norm = normalize_scope_selection(selection)
    if scope_kind == "volume":
        return meta.get("volume_index", 0) == norm["volume_index"]
    return meta.get("volume_index", 0) == norm["volume_index"] and meta.get("chapter_index", 0) == norm["chapter_index"]


# ---------------------------------------------------------------------------
# Structured payload extraction (from structured-parsers.js)
# ---------------------------------------------------------------------------

def get_generated_structured_payload(artifact: dict | None) -> dict | None:
    if not artifact:
        return None
    meta = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
    gen = meta.get("generated_payload")
    if isinstance(gen, dict) and isinstance(gen.get("structured"), dict):
        return gen["structured"]
    summary = (artifact.get("summary", {}) or {})
    if isinstance(summary, dict) and isinstance(summary.get("structured"), dict):
        return summary["structured"]
    return None


def parse_rough_volume_outline_volumes(snapshot: dict | None) -> list[dict]:
    """Parse volume entries from rough_volume_outline or outline artifact."""
    outline_artifact = get_artifact(snapshot, "rough_volume_outline") or get_artifact(snapshot, "outline")
    structured = get_generated_structured_payload(outline_artifact)

    if structured and isinstance(structured.get("volumes"), list) and structured["volumes"]:
        result = []
        for i, item in enumerate(structured["volumes"]):
            if not isinstance(item, dict):
                continue
            idx = int(item.get("volume_index") or i + 1)
            result.append({
                "index": idx,
                "title": str(item.get("title", "")).strip(),
                "goal": str(item.get("goal", "")).strip(),
                "conflict": str(item.get("main_conflict", "")).strip(),
                "hook": str(item.get("ending_hook", "")).strip(),
                "chapter_briefs": [
                    _clean_line(b) for b in (item.get("chapter_briefs") or [])
                    if isinstance(b, str) and b.strip()
                ],
                "target_chapter_count": int(item.get("target_chapter_count") or 0),
                "target_words": int(item.get("target_words") or 0),
            })
        return [r for r in result if r["index"] > 0]

    # Fallback: parse text content
    content = ""
    if outline_artifact:
        gen = (outline_artifact.get("metadata", {}) or {}).get("generated_payload", {}) or {}
        content = gen.get("content") or outline_artifact.get("content", "")
    text = str(content or "").strip()
    if not text:
        return []

    sections: list[dict] = []
    current: dict | None = None
    in_chapter_briefs = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = re.match(r"^第([一二三四五六七八九十百零两\d]+)卷[:：]\s*(.+)$", line)
        if m:
            if current:
                sections.append(current)
            current = {
                "index": _parse_chinese_number(m.group(1)),
                "title": m.group(2).strip(),
                "goal": "", "conflict": "", "hook": "",
                "chapter_briefs": [],
                "target_chapter_count": 0, "target_words": 0,
            }
            in_chapter_briefs = False
            continue

        if not current:
            continue

        gm = re.match(r"^[\-•*\s]*卷级目标[:：]\s*(.+)$", line)
        if gm:
            current["goal"] = gm.group(1).strip()
            continue
        cm = re.match(r"^[\-•*\s]*卷级冲突[:：]\s*(.+)$", line)
        if cm:
            current["conflict"] = cm.group(1).strip()
            continue
        hm = re.match(r"^[\-•*\s]*卷尾钩子[:：]\s*(.+)$", line)
        if hm:
            current["hook"] = hm.group(1).strip()
            continue

        if re.match(r"^[\-•*\s]*章节粗计划[:：]\s*$", line):
            in_chapter_briefs = True
            continue
        brief_m = re.match(r"^[\-•*\s]*章节粗计划[:：]\s*(.+)$", line)
        if brief_m:
            in_chapter_briefs = True
            b = _clean_line(brief_m.group(1))
            if b:
                current["chapter_briefs"].append(b)
            continue

        if in_chapter_briefs:
            b = _clean_line(line)
            if b:
                current["chapter_briefs"].append(b)

    if current:
        sections.append(current)
    return sections


def parse_rough_chapter_plan_chapters(snapshot: dict | None, volume_index: int = 1) -> list[dict]:
    """Parse chapter entries from rough_chapter_plan artifact for a given volume."""
    rough_artifact = get_scoped_artifact(snapshot, "rough_chapter_plan", {"volume_index": volume_index})
    structured = get_generated_structured_payload(rough_artifact)

    if structured and isinstance(structured.get("chapters"), list) and structured["chapters"]:
        result = []
        for i, item in enumerate(structured["chapters"]):
            if not isinstance(item, dict):
                continue
            idx = int(item.get("chapter_index") or i + 1)
            result.append({
                "index": idx,
                "title": str(item.get("title", "")).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "chapter_type": str(item.get("chapter_type", "")).strip(),
                "pov_character": str(item.get("pov_character", "")).strip(),
                "conflict": str(item.get("conflict", "")).strip(),
                "hook": str(item.get("hook", "")).strip(),
                "scene_summaries": [
                    _clean_line(s) for s in (item.get("scene_summaries") or [])
                    if isinstance(s, str) and s.strip()
                ],
                "main_event": str(item.get("main_event", "")).strip(),
                "target_words": int(item.get("target_words") or 0),
            })
        return [r for r in result if r["index"] > 0]

    # Fallback: parse text content
    content = ""
    if rough_artifact:
        gen = (rough_artifact.get("metadata", {}) or {}).get("generated_payload", {}) or {}
        content = gen.get("content") or rough_artifact.get("content", "")
    text = str(content or "").strip()
    if not text:
        return []

    chapters: list[dict] = []
    current: dict | None = None
    in_scenes = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = re.match(r"^第([一二三四五六七八九十百零两\d]+)章[:：]\s*(.+)$", line)
        if m:
            if current:
                chapters.append(current)
            current = {
                "index": _parse_chinese_number(m.group(1)),
                "title": m.group(2).strip(),
                "summary": "", "chapter_type": "", "pov_character": "",
                "conflict": "", "hook": "",
                "scene_summaries": [], "main_event": "", "target_words": 0,
            }
            in_scenes = False
            continue

        if not current:
            continue

        for pat, key in [
            (r"^[\-•*\s]*章节摘要[:：]\s*(.+)$", "summary"),
            (r"^[\-•*\s]*章节类型[:：]\s*(.+)$", "chapter_type"),
            (r"^[\-•*\s]*视角人物[:：]\s*(.+)$", "pov_character"),
            (r"^[\-•*\s]*核心冲突[:：]\s*(.+)$", "conflict"),
            (r"^[\-•*\s]*章节钩子[:：]\s*(.+)$", "hook"),
        ]:
            pm = re.match(pat, line)
            if pm:
                current[key] = pm.group(1).strip()
                break
        else:
            if re.match(r"^[\-•*\s]*(场景粗纲|场景摘要)[:：]\s*$", line):
                in_scenes = True
                continue
            sm = re.match(r"^[\-•*\s]*(场景粗纲|场景摘要)[:：]\s*(.+)$", line)
            if sm:
                in_scenes = True
                s = _clean_line(sm.group(2))
                if s:
                    current["scene_summaries"].append(s)
                continue
            if in_scenes:
                s = _clean_line(line)
                if s:
                    current["scene_summaries"].append(s)

    if current:
        chapters.append(current)
    return chapters


def get_rough_chapter_plan_chapter_count(snapshot: dict | None, volume_index: int = 1) -> int:
    rough_artifact = get_scoped_artifact(snapshot, "rough_chapter_plan", {"volume_index": volume_index})
    structured = get_generated_structured_payload(rough_artifact)
    if structured and isinstance(structured.get("chapters"), list) and structured["chapters"]:
        explicit = int(structured.get("total_target_chapters") or 0)
        return explicit if explicit > 0 else len(structured["chapters"])
    return len(parse_rough_chapter_plan_chapters(snapshot, volume_index))


# ---------------------------------------------------------------------------
# Volume / chapter entry options (from planning-defaults.js)
# ---------------------------------------------------------------------------

def get_volume_entry_options(snapshot: dict | None) -> list[dict]:
    volumes = parse_rough_volume_outline_volumes(snapshot)
    volumes.sort(key=lambda v: v["index"])
    result = []
    for v in volumes:
        label = f"第 {v['index']} 卷"
        if v["title"]:
            label += f" · {v['title']}"
        result.append({"value": str(v["index"]), "label": label})
    return result


def get_chapter_entry_options(snapshot: dict | None, volume_index: int = 1) -> list[dict]:
    chapters = parse_rough_chapter_plan_chapters(snapshot, volume_index)
    chapters.sort(key=lambda c: c["index"])
    result = []
    for c in chapters:
        label = f"第 {c['index']} 章"
        if c["title"]:
            label += f" · {c['title']}"
        result.append({"value": str(c["index"]), "label": label})
    return result


def get_selectable_volume_count(snapshot: dict | None) -> int:
    indices = [int(o["value"]) for o in get_volume_entry_options(snapshot)]
    return max(indices) if indices else 1


def get_selectable_chapter_count(snapshot: dict | None, volume_index: int = 1) -> int:
    indices = [int(o["value"]) for o in get_chapter_entry_options(snapshot, volume_index)]
    return max(indices) if indices else 1


def get_current_artifact_options(snapshot: dict | None, selection: dict | None = None) -> list[dict]:
    artifacts = list((snapshot or {}).get("artifacts", {}).values())
    norm = normalize_scope_selection(selection)

    def _rank(a: dict) -> int:
        meta = a.get("metadata", {}) or {}
        sk = meta.get("scope_kind", "project")
        if sk == "chapter" and meta.get("volume_index") == norm["volume_index"] and meta.get("chapter_index") == norm["chapter_index"]:
            return 0
        if sk == "volume" and meta.get("volume_index") == norm["volume_index"]:
            return 1
        if sk == "project":
            return 2
        return 3

    def _scope_label(a: dict) -> str:
        meta = a.get("metadata", {}) or {}
        sk = meta.get("scope_kind", "project")
        if sk == "chapter":
            return f"第 {meta.get('volume_index', 1)} 卷第 {meta.get('chapter_index', 1)} 章"
        if sk == "volume":
            return f"第 {meta.get('volume_index', 1)} 卷"
        return "全书"

    matching = [a for a in artifacts if _artifact_matches_selection(a, norm)]
    matching.sort(key=lambda a: (_rank(a), str(a.get("key", ""))))

    result = []
    for a in matching:
        step_key = _artifact_step_key(a)
        title = a.get("title") or get_step_label(step_key) or step_key or a.get("key", "未命名产物")
        result.append({
            "value": str(a.get("key") or step_key),
            "label": f"{title} · {_scope_label(a)} · {a.get('key', step_key)}",
        })
    return result


# ---------------------------------------------------------------------------
# Field option resolver (from planning-defaults.js)
# ---------------------------------------------------------------------------

def get_field_select_options(
    field: Any,  # FieldDef-like with option_source / options attrs
    snapshot: dict | None = None,
    selection: dict | None = None,
) -> list[dict]:
    option_source = getattr(field, "option_source", "")
    if option_source == "volume_entries":
        return get_volume_entry_options(snapshot)
    if option_source == "chapter_entries":
        norm = normalize_scope_selection(selection)
        return get_chapter_entry_options(snapshot, norm["volume_index"])
    if option_source == "current_artifacts":
        return get_current_artifact_options(snapshot, selection)
    options = getattr(field, "options", None) or []
    if options:
        result = []
        for o in options:
            if isinstance(o, str):
                result.append({"value": o, "label": o})
            else:
                v = str((o.get("value") or o.get("key") or "")).strip()
                l = str((o.get("label") or o.get("value") or o.get("key") or "")).strip()
                if l:
                    result.append({"value": v, "label": l, "disabled": bool(o.get("disabled"))})
        return result
    return []


# ---------------------------------------------------------------------------
# Default value resolution for fields (from planning-defaults.js getFieldDisplayValue)
# ---------------------------------------------------------------------------

PROJECT_NOTE_SOURCES: dict[str, list[str]] = {
    "requirements": ["core_requirements", "forbidden_elements"],
    "story_bible": ["tone", "style"],
    "characters": ["core_requirements", "forbidden_elements", "outline_focus"],
    "outline": ["outline_focus", "core_requirements", "forbidden_elements"],
    "rough_volume_outline": ["outline_focus", "core_requirements", "forbidden_elements"],
    "volume_outline": ["outline_focus", "core_requirements"],
    "rough_chapter_plan": ["outline_focus", "core_requirements"],
    "chapter_plan": ["core_requirements", "forbidden_elements"],
    "chapter": ["core_requirements", "forbidden_elements"],
    "revision": ["core_requirements", "forbidden_elements"],
    "consistency": ["outline_focus", "core_requirements", "forbidden_elements"],
    "memory": ["core_requirements", "forbidden_elements"],
}


def _collect_project_list_values(project_input: dict, keys: list[str]) -> list[str]:
    result = []
    for k in keys:
        v = project_input.get(k, [])
        if isinstance(v, list):
            result.extend([str(x).strip() for x in v if str(x).strip()])
    return result


def extract_volume_outline_defaults(snapshot: dict | None, volume_index: int = 1) -> dict | None:
    sections = parse_rough_volume_outline_volumes(snapshot)
    if not sections:
        return None
    safe = max(int(volume_index or 1), 1)
    selected = next((s for s in sections if s["index"] == safe), sections[0])
    if not selected:
        return None
    summary_parts = [p for p in [selected.get("goal", ""), selected.get("conflict", ""), selected.get("hook", "")] if p]
    return {
        "volume_title": selected.get("title", ""),
        "volume_summary": "；".join(summary_parts),
        "volume_goal": selected.get("goal", ""),
        "volume_conflict": selected.get("conflict", ""),
        "volume_hook": selected.get("hook", ""),
        "target_chapter_count": selected.get("target_chapter_count", 0),
    }


def extract_chapter_plan_defaults(snapshot: dict | None, volume_index: int = 1, chapter_index: int = 1) -> dict | None:
    chapters = parse_rough_chapter_plan_chapters(snapshot, volume_index)
    if not chapters:
        return None
    safe = max(int(chapter_index or 1), 1)
    selected = next((c for c in chapters if c["index"] == safe), chapters[0])
    if not selected:
        return None
    return {
        "volume_index": max(int(volume_index or 1), 1),
        "chapter_index": selected["index"],
        "chapter_title": selected.get("title", ""),
        "chapter_summary": selected.get("summary", ""),
        "chapter_type": selected.get("chapter_type", "主线推进章"),
        "pov_character": selected.get("pov_character", ""),
        "conflict": selected.get("conflict", ""),
        "hook": selected.get("hook", ""),
        "scene_summaries": selected.get("scene_summaries", []),
        "main_event": selected.get("main_event", ""),
        "target_words": selected.get("target_words", 0),
    }


def extract_chapter_draft_defaults(snapshot: dict | None, volume_index: int = 1, chapter_index: int = 1) -> dict | None:
    artifact = get_scoped_artifact(snapshot, "chapter_plan", {"volume_index": volume_index, "chapter_index": chapter_index})
    structured = get_generated_structured_payload(artifact)
    if not structured:
        return None
    scene_summaries = [
        str(s).strip() for s in (structured.get("scene_summaries") or [])
        if str(s).strip()
    ]
    continuity_notes = [
        str(n).strip() for n in (structured.get("continuity_notes") or [])
        if str(n).strip()
    ]
    writing_notes = [
        str(n).strip() for n in (structured.get("writing_notes") or [])
        if str(n).strip()
    ]
    return {
        "chapter_goal": str(structured.get("summary") or structured.get("main_event") or "").strip(),
        "scene_beats": scene_summaries,
        "notes": continuity_notes + writing_notes,
        "target_words": int(structured.get("target_words") or 0),
    }


def infer_chapter_count_for_volume(snapshot: dict | None, volume_index: int = 1) -> int:
    count = get_rough_chapter_plan_chapter_count(snapshot, volume_index)
    if count:
        return count
    defaults = extract_volume_outline_defaults(snapshot, volume_index)
    if defaults and defaults.get("target_chapter_count"):
        return defaults["target_chapter_count"]
    project = (snapshot or {}).get("project", {}) or {}
    pi = project.get("input", {}) or {}
    return pi.get("target_chapters_per_volume", 12)


def get_field_display_value(
    field: Any,  # FieldDef-like
    snapshot: dict | None = None,
    selection: dict | None = None,
) -> Any:
    """Resolve a sensible default value for a form field. Port of getFieldDisplayValue."""
    project = (snapshot or {}).get("project", {}) or {}
    pi = project.get("input", {}) or {}
    norm = normalize_scope_selection(selection)
    vi = norm["volume_index"]
    ci = norm["chapter_index"]
    step_key = getattr(field, "step_key", "") or getattr(field, "stepKey", "")

    key = field.key

    if key == "volume_index":
        return vi
    if key == "chapter_index":
        return ci
    if key == "requirements_text":
        return pi.get("premise", "")
    if key == "audience":
        return pi.get("target_audience", "")
    if key == "volume_count":
        return pi.get("target_volume_count", 1)
    if key == "chapters_per_volume":
        return infer_chapter_count_for_volume(snapshot, vi)

    if key == "target_artifact":
        chapter_artifact = get_scoped_artifact(snapshot, "chapter", {"volume_index": vi, "chapter_index": ci})
        artifact_options = get_current_artifact_options(snapshot, selection)
        return (chapter_artifact.get("key") if chapter_artifact else "") or (artifact_options[0]["value"] if artifact_options else "") or getattr(field, "default", "")

    # volume_outline step defaults
    if step_key == "volume_outline":
        defaults = extract_volume_outline_defaults(snapshot, vi)
        if defaults:
            if key in defaults:
                return defaults[key]

    # rough_chapter_plan step defaults
    if step_key == "rough_chapter_plan" and key == "target_chapter_count":
        return infer_chapter_count_for_volume(snapshot, vi)

    # chapter_plan step defaults
    if step_key == "chapter_plan":
        defaults = extract_chapter_plan_defaults(snapshot, vi, ci)
        if defaults and key in defaults:
            return defaults[key]

    # chapter step defaults
    if step_key == "chapter":
        defaults = extract_chapter_draft_defaults(snapshot, vi, ci)
        if defaults:
            if key in defaults:
                return defaults[key]
            if key == "notes" and defaults.get("notes"):
                return defaults["notes"] + _collect_project_list_values(pi, PROJECT_NOTE_SOURCES.get("chapter", []))

    # target_words inference
    if key == "target_words":
        volume_count = max(pi.get("target_volume_count", 1), 1)
        chapters_per_volume = max(infer_chapter_count_for_volume(snapshot, vi), 1)
        if step_key in ("chapter", "chapter_plan"):
            return max(int((pi.get("target_words", 0) or 0) / (volume_count * chapters_per_volume)), 2000)
        if step_key == "volume_outline":
            return max(int((pi.get("target_words", 0) or 0) / volume_count), 0)

    if key == "focus_points":
        return pi.get("outline_focus", [])
    if key == "known_rules":
        return _collect_project_list_values(pi, ["outline_focus", "core_requirements", "forbidden_elements"])

    if key == "notes" and step_key in PROJECT_NOTE_SOURCES:
        return _collect_project_list_values(pi, PROJECT_NOTE_SOURCES[step_key])

    default = getattr(field, "default", None)
    if default is not None and default != "":
        return default
    if getattr(field, "field_type", "") == "checkbox":
        return bool(getattr(field, "default", False))
    return ""


# ---------------------------------------------------------------------------
# Dependency / readiness checks (from artifact-selectors.js)
# ---------------------------------------------------------------------------

def _dependency_artifact_for(step: str, dependency: str, snapshot: dict | None, selection: dict | None = None) -> dict | None:
    dep_scope = get_step_scope_kind(dependency)
    norm = normalize_scope_selection(selection)
    sel: dict = {}
    if dep_scope == "volume":
        sel = {"volume_index": norm["volume_index"]}
    elif dep_scope == "chapter":
        sel = {"volume_index": norm["volume_index"], "chapter_index": norm["chapter_index"]}
    return get_scoped_artifact(snapshot, dependency, sel)


def get_dependency_states(step: str, snapshot: dict | None, selection: dict | None = None) -> list[dict]:
    dep_map = {e["key"]: e.get("depends_on", []) for e in FALLBACK_WORKFLOW_STEPS}
    deps = dep_map.get(step, [])
    result = []
    for dep in deps:
        artifact = _dependency_artifact_for(step, dep, snapshot, selection)
        if not artifact:
            status = "missing"
        elif artifact_is_stale(artifact):
            status = "stale"
        else:
            status = "active"
        result.append({"dependency": dep, "artifact": artifact, "status": status, "ready": status == "active"})
    return result


def get_step_readiness(step: str, snapshot: dict | None, selection: dict | None = None) -> dict:
    deps = get_dependency_states(step, snapshot, selection)
    missing = [d["dependency"] for d in deps if d["status"] == "missing"]
    stale = [d["dependency"] for d in deps if d["status"] == "stale"]
    return {"ready": not missing and not stale, "dependencies": deps, "missing": missing, "stale": stale}


def get_step_readiness_message(step: str, snapshot: dict | None, selection: dict | None = None) -> str:
    readiness = get_step_readiness(step, snapshot, selection)
    if readiness["ready"]:
        return ""
    parts = []
    if readiness["missing"]:
        labels = "、".join(get_step_label(d) for d in readiness["missing"])
        parts.append(f"缺失：{labels}")
    if readiness["stale"]:
        labels = "、".join(get_step_label(d) for d in readiness["stale"])
        parts.append(f"stale：{labels}")
    label = get_step_label(step)
    return f"{label}的前置依赖未就绪，{'；'.join(parts)}。请先处理这些步骤。"


def is_unlocked(step: str, snapshot: dict | None, selection: dict | None = None) -> bool:
    return get_step_readiness(step, snapshot, selection)["ready"]


def task_matches_step_selection(task: dict, step: str, selection: dict | None = None) -> bool:
    scope_kind = get_step_scope_kind(step)
    meta = task.get("metadata", {}) or {}
    task_scope = meta.get("scope_kind") or task.get("scope_kind", "project")
    task_vi = meta.get("volume_index") or task.get("volume_index")
    task_ci = meta.get("chapter_index") or task.get("chapter_index")

    if scope_kind == "project":
        return task_scope == "project"
    norm = normalize_scope_selection(selection)
    if scope_kind == "volume":
        return task_scope == "volume" and task_vi == norm["volume_index"]
    return task_scope == "chapter" and task_vi == norm["volume_index"] and task_ci == norm["chapter_index"]


def get_tasks_for_step_selection(step: str, tasks: list[dict], selection: dict | None = None) -> list[dict]:
    step_sel = selection_for_step(step, selection)
    return [t for t in tasks if t.get("task_name") == step and task_matches_step_selection(t, step, step_sel)]


def find_latest_task_for_step(step: str, tasks: list[dict], selection: dict | None = None) -> dict | None:
    matching = get_tasks_for_step_selection(step, tasks, selection)
    matching.sort(key=lambda t: str(t.get("created_at", "")), reverse=True)
    return matching[0] if matching else None


def get_step_status(step: str, snapshot: dict | None, tasks: list[dict], selection: dict | None = None) -> dict:
    artifact = get_artifact_for_step(snapshot, step, selection)
    if artifact:
        if artifact_is_stale(artifact):
            return {"tone": "warn", "text": "已失效"}
        return {"tone": "success", "text": "已产出"}

    latest_task = find_latest_task_for_step(step, tasks, selection)
    if latest_task:
        status = latest_task.get("status", "")
        if status == "failed":
            return {"tone": "danger", "text": "执行失败"}
        if status in ("pending", "running"):
            return {"tone": "accent", "text": "执行中"}

    readiness = get_step_readiness(step, snapshot, selection)
    if readiness["ready"]:
        return {"tone": "warn", "text": "待处理"}
    if readiness["stale"]:
        return {"tone": "warn", "text": "前置 stale"}
    return {"tone": "soft", "text": "未解锁"}


_BASE_ARTIFACT_PARENT: dict[str, tuple[str, str]] = {
    "volume_outline": ("rough_volume_outline", "volume"),
    "rough_chapter_plan": ("volume_outline", "volume"),
    "chapter_plan": ("rough_chapter_plan", "volume"),
    "chapter": ("chapter_plan", "chapter"),
}


def _artifact_dict(artifact: dict) -> dict:
    return {
        "key": artifact.get("key"),
        "title": artifact.get("title"),
        "content": artifact.get("content"),
        "summary": artifact.get("summary"),
        "metadata": artifact.get("metadata"),
    }


def build_base_artifact_payload(step: str, snapshot: dict | None, selection: dict | None = None) -> dict | None:
    """Attach parent artifact as base_artifact for scoped steps."""
    entry = _BASE_ARTIFACT_PARENT.get(step)
    if not entry:
        return None
    parent_step, parent_scope = entry
    norm = normalize_scope_selection(selection)
    sel: dict = {}
    if parent_scope == "volume":
        sel = {"volume_index": norm["volume_index"]}
    elif parent_scope == "chapter":
        sel = {"volume_index": norm["volume_index"], "chapter_index": norm["chapter_index"]}
    parent = get_scoped_artifact(snapshot, parent_step, sel)
    return _artifact_dict(parent) if parent else None
