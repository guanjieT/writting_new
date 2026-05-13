"""Unified workflow schema for GUI, Web UI and API clients.

The project previously had several parallel field definitions.  This module is a
single source of truth that can be serialized for any frontend.  It intentionally
keeps the existing workflow_spec.py dependency graph while adding field metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .workflow_spec import WORKFLOW_STEPS, workflow_dependency_map


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    field_type: str = "text"
    default: Any = ""
    required: bool = False
    rows: int = 1
    help_text: str = ""


@dataclass(frozen=True)
class StepSchema:
    key: str
    label: str
    scope: str
    page: str
    depends_on: tuple[str, ...] = ()
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)


COMMON_RUNTIME_FIELDS = (
    FieldSpec("temperature", "温度", "number", 0.7, rows=1, help_text="生成随机性，通常 0.5-0.9。"),
    FieldSpec("max_tokens", "最大输出 token", "number", 1200, rows=1, help_text="输出长度上限。"),
)


STEP_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    "requirements": (
        FieldSpec("requirements_text", "需求描述", "textarea", required=True, rows=6),
        FieldSpec("audience", "目标受众", "text"),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "story_bible": (
        FieldSpec("theme", "主题母题", "text"),
        FieldSpec("world_rules", "世界规则", "list", rows=5),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "characters": (
        FieldSpec("role_capacity", "核心角色规模", "number", 4),
        FieldSpec("core_roles", "核心角色", "list", rows=5),
        FieldSpec("role_slots", "角色槽位", "list", rows=5),
        FieldSpec("role_rules", "角色规则", "list", rows=5),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "outline": (
        FieldSpec("volume_count", "目标卷数", "number", 1, required=True),
        FieldSpec("chapters_per_volume", "每卷章节数", "number", 12, required=True),
        FieldSpec("focus_points", "总纲关注点", "list", rows=5),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "rough_volume_outline": (
        FieldSpec("volume_count", "目标卷数", "number", 1, required=True),
        FieldSpec("chapters_per_volume", "每卷章节数", "number", 12, required=True),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "volume_outline": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("volume_title", "卷标题", "text"),
        FieldSpec("volume_summary", "卷摘要", "textarea", rows=4),
        FieldSpec("volume_goal", "卷目标", "text"),
        FieldSpec("volume_conflict", "卷冲突", "text"),
        FieldSpec("volume_hook", "卷尾钩子", "text"),
        FieldSpec("target_words", "卷目标字数", "number", 0),
        FieldSpec("target_chapter_count", "卷目标章节数", "number", 12),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "rough_chapter_plan": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("target_chapter_count", "目标章节数", "number", 12, required=True),
        FieldSpec("total_target_chapters", "全卷章节总数", "number", 12),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "chapter_plan": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("chapter_index", "章序号", "number", 1, required=True),
        FieldSpec("chapter_title", "章节标题", "text"),
        FieldSpec("chapter_summary", "章节摘要", "textarea", rows=4),
        FieldSpec("chapter_type", "章节类型", "text"),
        FieldSpec("pov_character", "视角人物", "text"),
        FieldSpec("conflict", "核心冲突", "text"),
        FieldSpec("hook", "结尾钩子", "text"),
        FieldSpec("target_words", "目标字数", "number", 3000),
        FieldSpec("min_words", "最低字数", "number", 2400),
        FieldSpec("characters", "出场人物", "list", rows=4),
        FieldSpec("introduced_characters", "新登场人物", "list", rows=3),
        FieldSpec("scene_summaries", "场景摘要", "list", rows=6, help_text="建议 2-5 个场景，每行一个。"),
        FieldSpec("plan_notes", "计划备注", "textarea", rows=4),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "chapter": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("chapter_index", "章序号", "number", 1, required=True),
        FieldSpec("chapter_goal", "章节目标", "textarea", rows=3),
        FieldSpec("target_words", "目标字数", "number", 3000),
        FieldSpec("scene_beats", "场景节拍", "list", rows=6),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "revision": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("chapter_index", "章序号", "number", 1, required=True),
        FieldSpec("target_artifact", "修订目标", "select", required=True),
        FieldSpec("instruction", "修订指令", "textarea", rows=5, required=True),
        FieldSpec("focus_areas", "修订重点", "list", rows=4),
    ),
    "consistency": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("chapter_index", "章序号", "number", 1, required=True),
        FieldSpec("scope", "检查范围", "text", "chapter"),
        FieldSpec("known_rules", "已知规则", "list", rows=5),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
    "memory": (
        FieldSpec("volume_index", "卷序号", "number", 1, required=True),
        FieldSpec("chapter_index", "章序号", "number", 1, required=True),
        FieldSpec("query", "整理目标", "textarea", rows=3),
        FieldSpec("top_k", "记忆条数", "number", 10),
        FieldSpec("notes", "补充说明", "list", rows=4),
    ),
}


def step_schema(step_key: str) -> StepSchema:
    step = next(item for item in WORKFLOW_STEPS if item.key == step_key)
    return StepSchema(
        key=step.key,
        label=step.label,
        scope=step.scope,
        page=step.page,
        depends_on=step.depends_on,
        fields=STEP_FIELDS.get(step.key, ()) + COMMON_RUNTIME_FIELDS,
    )


def workflow_schema() -> dict[str, Any]:
    schemas = [step_schema(step.key) for step in WORKFLOW_STEPS]
    return {
        "steps": [
            {
                **asdict(schema),
                "fields": [asdict(field) for field in schema.fields],
            }
            for schema in schemas
        ],
        "dependencies": workflow_dependency_map(),
    }
