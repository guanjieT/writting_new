from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .domain import NovelProject
from .services import compact_artifact_context
from .services import _artifact_scope_payload, _scope_matches


def _project_brief(project: NovelProject) -> dict[str, Any]:
    project_input = project.input
    return {
        "project_id": project.project_id,
        "title": project_input.title,
        "genre": project_input.genre,
        "stage": project.status.value,
        "premise": project_input.premise,
        "target_words": project_input.target_words,
        "target_volume_count": project_input.target_volume_count,
        "target_chapters_per_volume": project_input.target_chapters_per_volume,
        "target_audience": project_input.target_audience,
        "tone": list(project_input.tone),
        "style": list(project_input.style),
        "outline_focus": list(project_input.outline_focus),
        "core_requirements": list(project_input.core_requirements),
        "forbidden_elements": list(project_input.forbidden_elements),
    }


def _project_input_payload(project: NovelProject) -> dict[str, Any]:
    return project.input.model_dump(mode="json")


def _step_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_payload = payload.get("payload")
    if isinstance(raw_payload, Mapping):
        return {key: value for key, value in raw_payload.items() if key not in {"temperature", "max_tokens"}}
    return {
        key: value
        for key, value in payload.items()
        if key not in {"temperature", "max_tokens", "payload"}
    }


def _completion_field_profile(step: str, field_key: str) -> dict[str, Any]:
    profiles: dict[tuple[str, str], dict[str, Any]] = {
        ("requirements", "requirements_text"): {
            "purpose": "补全需求描述",
            "focus": ["作品目标", "前提设定", "整体需求边界"],
            "output_mode": "输出可直接填写的需求描述",
            "project_keys": ["title", "genre", "premise", "target_words", "target_audience", "core_requirements", "forbidden_elements"],
            "step_keys": ["audience", "notes"],
        },
        ("requirements", "audience"): {
            "purpose": "补全目标受众",
            "focus": ["题材受众", "阅读预期", "表达策略"],
            "output_mode": "输出可直接填写的受众描述",
            "project_keys": ["title", "genre", "premise", "target_words", "target_audience"],
            "step_keys": ["requirements_text", "notes"],
        },
        ("requirements", "notes"): {
            "purpose": "补充需求阶段约束",
            "focus": ["禁忌元素", "项目边界", "必须满足的要求"],
            "output_mode": "输出补充说明或约束条目",
            "project_keys": ["core_requirements", "forbidden_elements", "premise", "target_audience"],
            "step_keys": ["requirements_text", "audience"],
        },
        ("story_bible", "theme"): {
            "purpose": "提炼主题母题",
            "focus": ["故事核心主题", "情绪基调", "长线表达方向"],
            "output_mode": "输出可直接填写的主题短语",
            "project_keys": ["title", "genre", "premise", "target_audience", "tone", "style"],
            "step_keys": ["world_rules", "notes"],
        },
        ("story_bible", "world_rules"): {
            "purpose": "补全世界规则",
            "focus": ["规则自洽", "能力体系", "社会运行逻辑"],
            "output_mode": "输出条目列表，优先保留可执行规则",
            "project_keys": ["title", "genre", "premise", "target_words", "target_audience", "tone", "style", "core_requirements", "forbidden_elements"],
            "step_keys": ["theme", "notes"],
        },
        ("story_bible", "notes"): {
            "purpose": "补充世界观说明",
            "focus": ["设定边界", "补充规则", "世界观风险提示"],
            "output_mode": "输出补充说明或约束条目",
            "project_keys": ["genre", "premise", "target_audience", "tone", "style", "core_requirements", "forbidden_elements"],
            "step_keys": ["theme", "world_rules"],
        },
        ("characters", "role_capacity"): {
            "purpose": "确认角色规模",
            "focus": ["核心角色数量", "角色槽位容量", "故事阶段长度"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_volume_count", "target_chapters_per_volume", "outline_focus", "core_requirements"],
            "step_keys": ["core_roles", "role_slots", "role_rules", "notes"],
        },
        ("characters", "core_roles"): {
            "purpose": "补全核心角色",
            "focus": ["主角/反派/关键支点", "角色关系", "必要稳定角色"],
            "output_mode": "输出角色列表",
            "project_keys": ["title", "genre", "premise", "target_audience", "outline_focus", "core_requirements", "forbidden_elements"],
            "step_keys": ["role_capacity", "role_slots", "role_rules", "notes"],
        },
        ("characters", "role_slots"): {
            "purpose": "补全角色槽位",
            "focus": ["可生长空间", "后续新增角色", "功能位预留"],
            "output_mode": "输出角色槽位列表",
            "project_keys": ["genre", "premise", "outline_focus", "core_requirements", "forbidden_elements"],
            "step_keys": ["role_capacity", "core_roles", "role_rules", "notes"],
        },
        ("characters", "role_rules"): {
            "purpose": "补全角色规则",
            "focus": ["角色增长约束", "角色变动边界", "角色上线规则"],
            "output_mode": "输出角色规则列表",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["role_capacity", "core_roles", "role_slots", "notes"],
        },
        ("characters", "notes"): {
            "purpose": "补充角色阶段约束",
            "focus": ["角色禁忌", "角色成长提醒", "人物功能边界"],
            "output_mode": "输出补充说明或约束条目",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_audience"],
            "step_keys": ["role_capacity", "core_roles", "role_slots", "role_rules"],
        },
        ("outline", "volume_count"): {
            "purpose": "确定全书卷数",
            "focus": ["作品体量", "题材节奏", "后续卷级拆分空间"],
            "output_mode": "只给出可直接填写的卷数或极简建议",
            "project_keys": ["target_words", "target_volume_count", "target_chapters_per_volume", "premise", "target_audience", "genre"],
            "step_keys": ["focus_points", "notes"],
        },
        ("outline", "chapters_per_volume"): {
            "purpose": "确定每卷章节密度",
            "focus": ["卷内节奏", "章节推进速度", "每卷承载的信息量"],
            "output_mode": "只给出可直接填写的章节数或极简建议",
            "project_keys": ["target_words", "target_volume_count", "target_chapters_per_volume", "premise", "target_audience", "genre"],
            "step_keys": ["volume_count", "focus_points", "notes"],
        },
        ("outline", "focus_points"): {
            "purpose": "提炼全书总纲关注点",
            "focus": ["主线升级节奏", "世界揭秘节点", "核心人物弧光", "全局冲突推进"],
            "output_mode": "输出条目列表，优先保留全书级关注点",
            "project_keys": ["title", "genre", "premise", "target_words", "target_volume_count", "target_chapters_per_volume", "target_audience", "tone", "style", "outline_focus", "core_requirements", "forbidden_elements"],
            "step_keys": ["volume_count", "chapters_per_volume"],
        },
        ("outline", "notes"): {
            "purpose": "补充总纲阶段的边界与提醒",
            "focus": ["未覆盖的约束", "题材禁忌", "全局风险提示"],
            "output_mode": "输出补充说明或约束条目，避免重复总纲正文",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "premise", "target_words", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_count", "chapters_per_volume", "focus_points"],
        },
        ("volume_outline", "volume_title"): {
            "purpose": "命名当前卷标题",
            "focus": ["卷内主题", "阶段感", "与全书主线的对应关系"],
            "output_mode": "输出可直接填写的卷标题",
            "project_keys": ["title", "genre", "premise", "target_volume_count", "target_chapters_per_volume", "outline_focus"],
            "step_keys": ["volume_index", "volume_summary", "volume_goal", "volume_conflict", "volume_hook", "target_chapter_count"],
        },
        ("volume_outline", "volume_summary"): {
            "purpose": "概括当前卷的整体弧线",
            "focus": ["卷目标", "核心冲突", "卷尾悬念"],
            "output_mode": "输出一段可直接填写的卷摘要",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "premise", "target_words", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_title", "volume_goal", "volume_conflict", "volume_hook", "target_chapter_count"],
        },
        ("volume_outline", "volume_goal"): {
            "purpose": "确定当前卷的主目标",
            "focus": ["本卷要完成的主要推进", "承接总纲的阶段目标"],
            "output_mode": "输出一句可直接填写的卷目标",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_title", "volume_summary", "volume_conflict", "volume_hook", "target_words", "target_chapter_count"],
        },
        ("volume_outline", "volume_conflict"): {
            "purpose": "明确当前卷冲突",
            "focus": ["外部对抗", "内部抉择", "卷级张力来源"],
            "output_mode": "输出可直接填写的卷冲突",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_title", "volume_summary", "volume_goal", "volume_hook", "target_words", "target_chapter_count"],
        },
        ("volume_outline", "volume_hook"): {
            "purpose": "设计当前卷尾钩子",
            "focus": ["下一卷承接点", "信息翻转", "悬念强度"],
            "output_mode": "输出可直接填写的卷尾钩子",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_title", "volume_summary", "volume_goal", "volume_conflict", "target_words", "target_chapter_count"],
        },
        ("volume_outline", "target_words"): {
            "purpose": "估算当前卷目标字数",
            "focus": ["卷目标规模", "节奏密度", "项目总字数目标"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_words", "target_volume_count", "target_chapters_per_volume", "outline_focus"],
            "step_keys": ["volume_title", "volume_summary", "volume_goal", "volume_conflict", "volume_hook", "target_chapter_count"],
        },
        ("volume_outline", "target_chapter_count"): {
            "purpose": "估算当前卷目标章节数",
            "focus": ["卷内结构拆分", "章节密度", "总纲章节配比"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_volume_count", "target_chapters_per_volume", "target_words", "outline_focus"],
            "step_keys": ["volume_title", "volume_summary", "volume_goal", "volume_conflict", "volume_hook", "target_words"],
        },
        ("volume_outline", "notes"): {
            "purpose": "补充当前卷写作约束",
            "focus": ["卷内特殊规则", "角色调度提醒", "结构性注意事项"],
            "output_mode": "输出补充说明或约束条目",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_title", "volume_summary", "volume_goal", "volume_conflict", "volume_hook", "target_words", "target_chapter_count"],
        },
        ("rough_chapter_plan", "target_chapter_count"): {
            "purpose": "确认当前卷章节总数",
            "focus": ["卷级拆分规模", "粗章纲覆盖范围"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_volume_count", "target_chapters_per_volume", "outline_focus"],
            "step_keys": ["volume_index", "notes"],
        },
        ("chapter_plan", "chapter_title"): {
            "purpose": "命名当前章标题",
            "focus": ["章节功能", "本章情绪", "和卷纲的承接"],
            "output_mode": "输出可直接填写的章节标题",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_summary", "chapter_type", "pov_character", "conflict", "hook", "target_words", "min_words", "characters", "introduced_characters", "scene_summaries", "plan_notes"],
        },
        ("chapter_plan", "chapter_summary"): {
            "purpose": "概括当前章内容",
            "focus": ["章节目标", "事件推进", "人物变化"],
            "output_mode": "输出一段可直接填写的章节摘要",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_type", "pov_character", "conflict", "hook", "target_words", "min_words", "characters", "introduced_characters", "scene_summaries", "plan_notes"],
        },
        ("chapter_plan", "chapter_type"): {
            "purpose": "判断章节类型",
            "focus": ["推进章", "冲突章", "过渡章", "爆点章"],
            "output_mode": "输出简洁的章节类型标签",
            "project_keys": ["outline_focus", "core_requirements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "pov_character", "conflict", "hook", "characters", "scene_summaries"],
        },
        ("chapter_plan", "pov_character"): {
            "purpose": "确定本章视角人物",
            "focus": ["叙事重心", "本章信息可见范围"],
            "output_mode": "输出可直接填写的人物名",
            "project_keys": ["outline_focus", "core_requirements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_summary", "chapter_type", "characters", "introduced_characters", "scene_summaries"],
        },
        ("chapter_plan", "conflict"): {
            "purpose": "补强本章核心冲突",
            "focus": ["本章矛盾焦点", "阻力来源", "行动目标"],
            "output_mode": "输出可直接填写的核心冲突",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "hook", "characters", "introduced_characters", "scene_summaries"],
        },
        ("chapter_plan", "hook"): {
            "purpose": "设计本章结尾钩子",
            "focus": ["下一章承接", "信息翻转", "悬念保留"],
            "output_mode": "输出可直接填写的章节钩子",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "conflict", "characters", "scene_summaries"],
        },
        ("chapter_plan", "target_words"): {
            "purpose": "估算本章目标字数",
            "focus": ["章节容量", "情节密度"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_words", "target_volume_count", "target_chapters_per_volume", "outline_focus"],
            "step_keys": ["volume_index", "chapter_index", "chapter_summary", "chapter_type", "scene_summaries"],
        },
        ("chapter_plan", "min_words"): {
            "purpose": "估算本章最低字数",
            "focus": ["最低完整表达", "不压缩到失去事件推进"],
            "output_mode": "只输出数字或极简建议",
            "project_keys": ["target_words", "target_volume_count", "target_chapters_per_volume", "outline_focus"],
            "step_keys": ["volume_index", "chapter_index", "chapter_summary", "chapter_type", "scene_summaries"],
        },
        ("chapter_plan", "characters"): {
            "purpose": "确定本章出场人物",
            "focus": ["本章必要角色", "视角相关人物", "避免无关角色堆叠"],
            "output_mode": "输出角色列表",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "introduced_characters", "scene_summaries", "plan_notes"],
        },
        ("chapter_plan", "introduced_characters"): {
            "purpose": "确定本章新人物",
            "focus": ["首次登场人物", "剧情功能"],
            "output_mode": "输出新人物列表或空列表建议",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "characters", "scene_summaries", "plan_notes"],
        },
        ("chapter_plan", "scene_summaries"): {
            "purpose": "拆解本章场景",
            "focus": ["场景推进顺序", "场景之间的因果关系", "节奏起伏"],
            "output_mode": "输出场景列表",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "conflict", "hook", "characters", "introduced_characters"],
        },
        ("chapter_plan", "plan_notes"): {
            "purpose": "补充章节计划备注",
            "focus": ["执行提醒", "结构风险", "写作注意事项"],
            "output_mode": "输出补充说明",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "conflict", "hook", "characters", "introduced_characters", "scene_summaries"],
        },
        ("chapter_plan", "notes"): {
            "purpose": "补充章节层约束",
            "focus": ["角色限制", "情节边界", "和卷纲的衔接提醒"],
            "output_mode": "输出补充说明或约束条目",
            "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_volume_count", "target_chapters_per_volume"],
            "step_keys": ["volume_index", "chapter_index", "chapter_title", "chapter_summary", "chapter_type", "pov_character", "conflict", "hook", "characters", "introduced_characters", "scene_summaries", "plan_notes"],
        },
    }
    return profiles.get((step, field_key), {
        "purpose": "补全当前字段",
        "focus": [],
        "output_mode": "输出可直接填写的字段内容",
        "project_keys": ["outline_focus", "core_requirements", "forbidden_elements", "target_words", "target_volume_count", "target_chapters_per_volume"],
        "step_keys": [],
    })


def _pick_payload_fields(payload: Mapping[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload.get(key) for key in keys if key in payload}


def _project_input_fields(project: NovelProject, keys: list[str]) -> dict[str, Any]:
    project_input = project.input.model_dump(mode="json")
    return {key: project_input.get(key) for key in keys if key in project_input}


def _completion_reference_fields(project: NovelProject, payload: Mapping[str, Any], step_payload_without_current_field: dict[str, Any]) -> dict[str, Any]:
    step = str(payload.get("step", ""))
    field_key = str(payload.get("field_key", ""))
    profile = _completion_field_profile(step, field_key)
    reference_steps = profile.get("step_keys", [])
    reference_project_keys = profile.get("project_keys", [])
    return {
        "purpose": profile.get("purpose", ""),
        "focus": profile.get("focus", []),
        "output_mode": profile.get("output_mode", ""),
        "project_fields": _project_input_fields(project, list(reference_project_keys)),
        "step_fields": _pick_payload_fields(step_payload_without_current_field, list(reference_steps)),
        "step_fields_with_current": _pick_payload_fields(_step_payload(payload), list(reference_steps) + [field_key]),
    }


def _selected_artifacts(project: NovelProject, step_keys: list[str], payload: Mapping[str, Any], *, excerpt_chars: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for step_key in step_keys:
        artifact = next(
            (
                candidate
                for candidate in project.artifacts.values()
                if _scope_matches(candidate, step_key, _artifact_scope_payload(step_key, payload))
            ),
            None,
        )
        if artifact is not None:
            context = compact_artifact_context(artifact, excerpt_chars=excerpt_chars, include_excerpt=excerpt_chars > 0)
            summary = context.get("summary")
            if isinstance(summary, Mapping):
                structured = summary.get("structured")
                if isinstance(structured, Mapping):
                    context["structured"] = dict(structured)
            result[step_key] = context
    return result


@dataclass(frozen=True)
class GenerationContextProfile:
    name: str
    artifact_keys: tuple[str, ...]
    artifact_excerpt_chars: int = 0
    context_type: str = "general"


GENERATION_CONTEXT_PROFILES: dict[str, GenerationContextProfile] = {
    "requirements": GenerationContextProfile("requirements", (), context_type="short"),
    "story_bible": GenerationContextProfile("story_bible", ("requirements",), artifact_excerpt_chars=120, context_type="short"),
    "characters": GenerationContextProfile("characters", ("requirements", "story_bible"), artifact_excerpt_chars=120, context_type="short"),
    "outline": GenerationContextProfile("outline", ("requirements", "story_bible", "characters"), artifact_excerpt_chars=0, context_type="brief"),
    "rough_volume_outline": GenerationContextProfile("rough_volume_outline", ("outline",), artifact_excerpt_chars=0, context_type="expanded"),
    "volume_outline": GenerationContextProfile("volume_outline", ("rough_volume_outline", "outline"), artifact_excerpt_chars=0, context_type="expanded"),
    "rough_chapter_plan": GenerationContextProfile("rough_chapter_plan", ("volume_outline", "rough_volume_outline", "outline"), artifact_excerpt_chars=0, context_type="expanded"),
    "chapter_plan": GenerationContextProfile("chapter_plan", ("rough_chapter_plan", "volume_outline", "outline"), artifact_excerpt_chars=0, context_type="expanded"),
    "chapter": GenerationContextProfile("chapter", ("chapter_plan", "rough_chapter_plan", "volume_outline", "outline"), artifact_excerpt_chars=0, context_type="expanded"),
    "revision": GenerationContextProfile("revision", ("chapter", "chapter_plan"), artifact_excerpt_chars=220, context_type="focused"),
    "consistency": GenerationContextProfile("consistency", ("chapter", "chapter_plan", "story_bible", "characters"), artifact_excerpt_chars=180, context_type="focused"),
    "memory": GenerationContextProfile("memory", ("chapter", "revision", "consistency"), artifact_excerpt_chars=140, context_type="focused"),
}


def build_generation_context(project: NovelProject, step: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    profile = GENERATION_CONTEXT_PROFILES.get(step, GenerationContextProfile(step, ()))
    return {
        "step": step,
        "context_type": profile.context_type,
        "project_brief": _project_brief(project),
        "project_input": _project_input_payload(project),
        "step_payload": _step_payload(payload),
        "selected_artifacts": _selected_artifacts(project, list(profile.artifact_keys), payload, excerpt_chars=profile.artifact_excerpt_chars),
    }


def build_completion_context(project: NovelProject, payload: Mapping[str, Any], direct_dependency_steps: list[str]) -> dict[str, Any]:
    current_field_key = str(payload.get("field_key", ""))
    selected_artifacts = _selected_artifacts(project, direct_dependency_steps, payload, excerpt_chars=180)
    step_payload = _step_payload(payload)
    step_payload_without_current_field = {key: value for key, value in step_payload.items() if key != current_field_key}
    field_context = {
        "key": str(payload.get("field_key", "")),
        "label": str(payload.get("field_label", "")),
        "type": str(payload.get("field_type", "text")),
        "placeholder": str(payload.get("field_placeholder", "")),
        "current_value": str(payload.get("current_value", "")),
    }
    return {
        "step": str(payload.get("step", "")),
        "field": field_context,
        "step_payload": step_payload_without_current_field,
        "step_payload_with_field": step_payload,
        "reference_fields": _completion_reference_fields(project, payload, step_payload_without_current_field),
        "direct_dependency_steps": direct_dependency_steps,
        "direct_dependency_artifacts": selected_artifacts,
        "project_brief": _project_brief(project),
        "project_input": _project_input_payload(project),
    }


def build_stage_summary(project: NovelProject, step: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    context = build_generation_context(project, step, payload)
    return {
        "project_brief": context["project_brief"],
        "project_input": context["project_input"],
        "step_payload": context["step_payload"],
        "selected_artifacts": context["selected_artifacts"],
        "context_type": context["context_type"],
    }