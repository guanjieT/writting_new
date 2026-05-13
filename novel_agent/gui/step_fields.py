"""Step field definitions — Python port of step-meta.js."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Field type constants
# ---------------------------------------------------------------------------

FIELD_TEXT = "text"
FIELD_TEXTAREA = "textarea"
FIELD_NUMBER = "number"
FIELD_SELECT = "select"
FIELD_CHECKBOX = "checkbox"
FIELD_LIST = "list"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FieldDef:
    key: str
    label: str
    field_type: str = FIELD_TEXT
    rows: int = 0
    placeholder: str = ""
    default: Any = None
    advanced: bool = False
    is_list: bool = False  # newline-separated list
    step_: float = 0.1  # for number fields
    options: list[dict] = field(default_factory=list)
    option_source: str = ""  # volume_entries | chapter_entries | current_artifacts
    disabled: bool = False
    empty_label: str = ""


@dataclass
class StepDef:
    key: str
    label: str
    group: str
    page: str  # workflow | outline | volume-outline | chapter-plan
    description: str = ""
    object_name: str = ""
    review_points: list[str] = field(default_factory=list)
    fields: list[FieldDef] = field(default_factory=list)
    depends_on: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Step group definitions
# ---------------------------------------------------------------------------

PAGE_STEP_GROUPS: dict[str, list[dict]] = {
    "workflow": [
        {"key": "setting", "label": "设定资产", "steps": ["requirements", "story_bible", "characters"]},
        {"key": "structure-outline", "label": "全书结构", "steps": ["outline", "rough_volume_outline"]},
        {"key": "structure-volume", "label": "卷级结构", "steps": ["volume_outline", "rough_chapter_plan"]},
        {"key": "structure-chapter", "label": "章节结构", "steps": ["chapter_plan"]},
        {"key": "writing", "label": "正文与审查", "steps": ["chapter", "revision", "consistency", "memory"]},
    ],
}

REVIEW_GROUPS: list[dict] = [
    {"key": "setting", "label": "设定资产", "steps": ["requirements", "story_bible", "characters"]},
    {"key": "structure-outline", "label": "总纲与粗卷纲", "steps": ["outline", "rough_volume_outline"]},
    {"key": "structure-volume", "label": "卷纲与粗章纲", "steps": ["volume_outline", "rough_chapter_plan"]},
    {"key": "structure-chapter", "label": "章节计划", "steps": ["chapter_plan"]},
    {"key": "writing", "label": "正文与修订", "steps": ["chapter", "revision"]},
    {"key": "audit", "label": "一致性与记忆", "steps": ["consistency", "memory"]},
]

FALLBACK_WORKFLOW_STEPS: list[dict] = [
    {"key": "requirements", "label": "需求分析", "depends_on": []},
    {"key": "story_bible", "label": "世界观设定", "depends_on": ["requirements"]},
    {"key": "characters", "label": "角色框架", "depends_on": ["requirements", "story_bible"]},
    {"key": "outline", "label": "总纲", "depends_on": ["requirements", "story_bible", "characters"]},
    {"key": "rough_volume_outline", "label": "粗卷纲", "depends_on": ["outline"]},
    {"key": "volume_outline", "label": "完善卷纲", "depends_on": ["rough_volume_outline"]},
    {"key": "rough_chapter_plan", "label": "粗章纲", "depends_on": ["volume_outline"]},
    {"key": "chapter_plan", "label": "完善章节计划", "depends_on": ["rough_chapter_plan"]},
    {"key": "chapter", "label": "章节生成", "depends_on": ["chapter_plan"]},
    {"key": "revision", "label": "修订", "depends_on": ["chapter"]},
    {"key": "consistency", "label": "一致性检查", "depends_on": ["chapter"]},
    {"key": "memory", "label": "记忆整理", "depends_on": ["chapter"]},
]


def _f(key: str, label: str, field_type: str = FIELD_TEXT, **kw: Any) -> FieldDef:
    return FieldDef(key=key, label=label, field_type=field_type, **kw)


# ---------------------------------------------------------------------------
# All 12 step definitions
# ---------------------------------------------------------------------------

STEP_DEFS: dict[str, StepDef] = {
    "requirements": StepDef(
        key="requirements",
        label="需求定位",
        group="setting",
        page="workflow",
        description="把作品目标、边界和必须满足的约束先说清楚，避免后面所有环节都建立在模糊前提上。",
        object_name="作品需求单",
        review_points=["主目标是否单一明确", "受众定位是否清晰", "禁忌与硬约束是否已经落地"],
        fields=[
            _f("requirements_text", "需求描述", FIELD_TEXTAREA, rows=6, placeholder="这本书最想实现什么？要解决什么写作目标？"),
            _f("audience", "目标受众", placeholder="例如：男频成长流读者 / 女性向群像读者"),
            _f("notes", "补充约束", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="一行一条，例如：\n必须有家族权力斗争\n不能采用第一人称"),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1200, advanced=True),
        ],
    ),
    "story_bible": StepDef(
        key="story_bible",
        label="世界与规则",
        group="setting",
        page="workflow",
        description="把世界规则、主题母题和运行逻辑沉淀为故事圣经，方便后续角色与结构统一。",
        object_name="世界观资产",
        review_points=["世界规则是否可执行", "主题是否和题材匹配", "设定是否已经足够支撑长篇推进"],
        fields=[
            _f("theme", "主题母题", placeholder="例如：权力的代价 / 失序世界中的重建"),
            _f("world_rules", "世界规则", FIELD_TEXTAREA, rows=6, is_list=True, placeholder="一行一条，例如：\n修炼体系分九阶\n货币与灵石绑定"),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="对社会结构、力量来源、势力边界的补充说明"),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1200, advanced=True),
        ],
    ),
    "characters": StepDef(
        key="characters",
        label="角色框架",
        group="setting",
        page="workflow",
        description="先固定核心角色，再保留可生长角色槽位，避免开局把所有人物锁死。",
        object_name="角色框架",
        review_points=["男女主和终反派是否明确", "角色槽位是否保留了后续生长空间", "角色规则是否足够稳定"],
        fields=[
            _f("role_capacity", "角色容量参考", FIELD_NUMBER, default=4, placeholder="只做规模提示，不是硬性上限"),
            _f("core_roles", "核心角色", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="一行一位，优先填男女主、最终反派、必需支点角色"),
            _f("role_slots", "角色槽位", FIELD_TEXTAREA, rows=5, is_list=True, placeholder="一行一个槽位，例如：导师位 / 竞争者位 / 线人位 / 牺牲者位"),
            _f("role_rules", "角色生长规则", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="一行一条，例如：\n每卷最多新增两个长期角色\n新角色必须对应具体剧情事件"),
            _f("notes", "角色补充约束", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="例如：女主不能工具化；终反派必须有完整利益逻辑"),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1200, advanced=True),
        ],
    ),
    "outline": StepDef(
        key="outline",
        label="总纲",
        group="structure",
        page="outline",
        description="先定义全书级别的目标、节奏和阶段推进，再为后续粗卷纲提供总蓝图。",
        object_name="总纲",
        review_points=["开端—发展—转折—收束是否成链", "全书目标与题材预期是否一致", "是否足以支撑后续卷级拆解"],
        fields=[
            _f("volume_count", "目标卷数", FIELD_NUMBER, default=1),
            _f("chapters_per_volume", "每卷章节数", FIELD_NUMBER, default=12),
            _f("focus_points", "总纲关注点", FIELD_TEXTAREA, rows=5, is_list=True, placeholder="例如：主线升级节奏、世界揭秘节点、核心人物弧光"),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1400, advanced=True),
        ],
    ),
    "rough_volume_outline": StepDef(
        key="rough_volume_outline",
        label="粗卷纲",
        group="structure",
        page="outline",
        description="一次生成全书所有卷的粗略结构，不拆成单卷。",
        object_name="粗卷纲",
        review_points=["是否覆盖所有卷", "卷间节奏是否连贯", "每卷是否保留后续细化空间"],
        fields=[
            _f("volume_count", "目标卷数", FIELD_NUMBER, default=1),
            _f("chapters_per_volume", "每卷章节数", FIELD_NUMBER, default=12),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1600, advanced=True),
        ],
    ),
    "volume_outline": StepDef(
        key="volume_outline",
        label="完善卷纲",
        group="structure",
        page="volume-outline",
        description="基于粗卷纲，完善当前卷的完整卷纲。",
        object_name="卷纲",
        review_points=["卷目标是否独立完整", "是否与粗卷纲对应", "是否可直接进入粗章纲阶段"],
        fields=[
            _f("volume_index", "卷序号", FIELD_SELECT, option_source="volume_entries", default=1, disabled=True),
            _f("volume_title", "卷标题", placeholder="例如：第一卷·入局"),
            _f("volume_summary", "卷摘要", FIELD_TEXTAREA, rows=5),
            _f("volume_goal", "卷目标"),
            _f("volume_conflict", "卷冲突", FIELD_TEXTAREA, rows=4),
            _f("volume_hook", "卷尾钩子", FIELD_TEXTAREA, rows=3),
            _f("target_words", "卷目标字数", FIELD_NUMBER, default=0),
            _f("target_chapter_count", "卷目标章节数", FIELD_NUMBER, default=0),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1400, advanced=True),
        ],
    ),
    "rough_chapter_plan": StepDef(
        key="rough_chapter_plan",
        label="粗章纲",
        group="structure",
        page="volume-outline",
        description="一次生成当前卷所有章节的粗计划。",
        object_name="粗章纲",
        review_points=["卷内章节节奏是否成链", "章节之间是否有铺垫和呼应", "是否保留了细化空间"],
        fields=[
            _f("volume_index", "卷序号", FIELD_SELECT, option_source="volume_entries", default=1, disabled=True),
            _f("target_chapter_count", "章节数", FIELD_NUMBER, default=0),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1600, advanced=True),
        ],
    ),
    "chapter_plan": StepDef(
        key="chapter_plan",
        label="完善章节计划",
        group="structure",
        page="chapter-plan",
        description="基于粗章纲，完善当前章的完整章节计划。",
        object_name="章节计划",
        review_points=["章节目标是否单一", "是否与粗章纲对应", "是否已细化到可直接写作"],
        fields=[
            _f("volume_index", "卷序号", FIELD_SELECT, option_source="volume_entries", default=1, disabled=True),
            _f("chapter_index", "章节条目", FIELD_SELECT, option_source="chapter_entries", default=1, disabled=True),
            _f("chapter_title", "章节标题"),
            _f("chapter_summary", "章节摘要", FIELD_TEXTAREA, rows=5),
            _f("chapter_type", "章节类型", default="主线推进章"),
            _f("pov_character", "视角人物"),
            _f("protagonist_present", "主角在场", FIELD_CHECKBOX, default=True),
            _f("conflict", "核心冲突", FIELD_TEXTAREA, rows=3),
            _f("hook", "章节钩子", FIELD_TEXTAREA, rows=3),
            _f("target_words", "目标字数", FIELD_NUMBER, default=3000),
            _f("min_words", "最低字数", FIELD_NUMBER, default=2000),
            _f("characters", "本章人物", FIELD_TEXTAREA, rows=3, is_list=True),
            _f("introduced_characters", "新登场人物", FIELD_TEXTAREA, rows=3, is_list=True),
            _f("scene_summaries", "场景摘要", FIELD_TEXTAREA, rows=5, is_list=True),
            _f("plan_notes", "计划备注", FIELD_TEXTAREA, rows=3),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=3, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=2000, advanced=True),
        ],
    ),
    "chapter": StepDef(
        key="chapter",
        label="章节正文",
        group="writing",
        page="workflow",
        description="这里只负责把已确认的章节计划落成正文，不再承担结构探索。",
        object_name="章节正文",
        review_points=["本章目标是否落地", "节奏是否符合章节计划", "场景推进是否清晰"],
        fields=[
            _f("volume_index", "卷序号", FIELD_SELECT, option_source="volume_entries", default=1, disabled=True),
            _f("chapter_index", "章节条目", FIELD_SELECT, option_source="chapter_entries", default=1, disabled=True),
            _f("chapter_goal", "章节目标", placeholder="一句话写清本章完成什么推进"),
            _f("target_words", "目标字数", FIELD_NUMBER, default=2000),
            _f("scene_beats", "场景节拍", FIELD_TEXTAREA, rows=5, is_list=True, placeholder="一行一段节拍，例如：\n遭遇伏击\n被迫结盟\n留下误导线索"),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=4000, advanced=True),
        ],
    ),
    "revision": StepDef(
        key="revision",
        label="正文修订",
        group="writing",
        page="workflow",
        description="修订是针对已有正文的质量调整，不是重新生成世界观或总纲。",
        object_name="修订结果",
        review_points=["修订目标是否具体", "是否只改需要改的部分", "是否保住了原有结构作用"],
        fields=[
            _f("target_artifact", "目标产物键", FIELD_SELECT, option_source="current_artifacts", default="chapter", empty_label="当前范围暂无可选产物"),
            _f("instruction", "修订指令", FIELD_TEXTAREA, rows=5, placeholder="例如：压缩说明性段落，增强人物对话中的冲突感"),
            _f("focus_areas", "修订关注点", FIELD_TEXTAREA, rows=4, is_list=True, placeholder="一行一条，例如：\n节奏\n人物动机\n结尾钩子"),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1200, advanced=True),
        ],
    ),
    "consistency": StepDef(
        key="consistency",
        label="一致性检查",
        group="review",
        page="workflow",
        description="把角色、设定、时间线和正文进行交叉检查，找出冲突点。",
        object_name="一致性报告",
        review_points=["是否覆盖设定与人物", "是否指出具体冲突", "问题是否可追溯到上游资产"],
        fields=[
            _f(
                "scope",
                "检查范围",
                FIELD_SELECT,
                default="project",
                options=[
                    {"value": "project", "label": "全书范围"},
                    {"value": "volume", "label": "当前卷范围"},
                    {"value": "chapter", "label": "当前章范围"},
                ],
            ),
            _f("known_rules", "已知规则", FIELD_TEXTAREA, rows=5, is_list=True, placeholder="可填已知设定规则，帮助报告更聚焦"),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1200, advanced=True),
        ],
    ),
    "memory": StepDef(
        key="memory",
        label="记忆整理",
        group="review",
        page="workflow",
        description="把已生成内容里的关键信息重新组织出来，方便后续长篇续写时检索。",
        object_name="记忆摘要",
        review_points=["是否抓到关键事实", "是否方便后续引用", "是否遗漏关键角色与规则"],
        fields=[
            _f("query", "检索问题", placeholder="例如：主角在第一卷中已暴露了哪些秘密？"),
            _f("top_k", "返回条目数", FIELD_NUMBER, default=5),
            _f("notes", "补充说明", FIELD_TEXTAREA, rows=4, is_list=True),
            _f("temperature", "生成温度", FIELD_NUMBER, step_=0.1, default=0.7, advanced=True),
            _f("max_tokens", "最大输出", FIELD_NUMBER, default=1000, advanced=True),
        ],
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_STEP_KEYS = list(STEP_DEFS.keys())

STATUS_COLORS: dict[str, str] = {
    "success": "#15803d",
    "warn": "#b45309",
    "danger": "#b42318",
    "accent": "#0369a1",
    "soft": "#667085",
}


def get_step_def(step_key: str) -> StepDef:
    return STEP_DEFS.get(step_key, StepDef(key=step_key, label=step_key, group="", page="workflow"))


def get_step_label(step_key: str) -> str:
    return get_step_def(step_key).label


def get_step_dependencies(step_key: str) -> tuple[str, ...]:
    for entry in FALLBACK_WORKFLOW_STEPS:
        if entry["key"] == step_key:
            return tuple(entry.get("depends_on", []))
    return ()


def get_dependency_map() -> dict[str, list[str]]:
    return {entry["key"]: entry.get("depends_on", []) for entry in FALLBACK_WORKFLOW_STEPS}


def workflow_step_spec() -> dict:
    return {
        "steps": [{"key": s["key"], "label": s["label"], "depends_on": s.get("depends_on", [])} for s in FALLBACK_WORKFLOW_STEPS],
        "dependencies": get_dependency_map(),
    }
