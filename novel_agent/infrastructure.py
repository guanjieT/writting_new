from __future__ import annotations

import json
import re
from json import JSONDecodeError
import threading
from pathlib import Path
from typing import Any
from urllib import error, request

from .domain import AuditEvent, AuditSink, LLMProvider, NovelProject, ProjectRepository, PromptStore, TaskRecord, TaskStore, TaskStatus


def _safe_key(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not value or any(character not in allowed for character in value):
        raise ValueError(f"unsafe key: {value!r}")
    return value


class FileProjectRepository(ProjectRepository):
    def __init__(self, projects_dir: str | Path):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self.projects_dir / f"{_safe_key(project_id)}.json"

    def list(self) -> list[NovelProject]:
        items: list[NovelProject] = []
        for path in sorted(self.projects_dir.glob("*.json")):
            items.append(NovelProject.model_validate_json(path.read_text(encoding="utf-8")))
        return items

    def get(self, project_id: str) -> NovelProject | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return NovelProject.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, project: NovelProject) -> NovelProject:
        path = self._path(project.project_id)
        path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        return project

    def delete(self, project_id: str) -> NovelProject | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        project = NovelProject.model_validate_json(path.read_text(encoding="utf-8"))
        path.unlink()
        return project


class FilePromptStore(PromptStore):
    DEFAULT_TEMPLATES: dict[str, str] = {
        "requirements": "你是小说需求分析助手。根据项目输入和当前需求表单，生成需求正文，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，允许分段，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n- 如果某项为空，输出空字符串或空数组，不要编造。\n\n项目：{project_summary}\n项目输入：{input_json}\n项目简报：{project_brief_json}\n当前需求表单：{context_json}\n\nJSON：",
        "story_bible": "你是世界观设计助手。请生成世界规则、核心设定、冲突结构与可持续展开点，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n- 如果某项为空，输出空字符串或空数组，不要编造。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "characters": "你是角色框架设计助手。请先固定男女主、终极反派和少数必要核心角色，再为后续剧情预留可生长的角色槽位，不要一次性锁死全部角色，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n- 核心角色只保留必须稳定的角色；其余角色优先以槽位或候选形式表达。\n- 如果当前输入只够确定少数核心角色，就明确说明哪些角色暂缓确定。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n角色框架：{character_frame_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "outline": "你是小说总纲助手。请先生成全书总纲，输出必须以结构化字段为主体。content 只是简短摘要，不要承载主数据。\n\n要求：\n- 只输出 JSON。\n- 顶层必须包含 content、overview、key_facts、constraints、open_questions、best_for_reason、structured。\n- content 只写 3~6 行的全书摘要，不要重复 structured 里的字段。\n- structured 是主体，必须包含 story_arcs、global_goals、main_conflicts、ending_direction、volume_plan_hints。\n- 这些核心键不得省略；缺失时用空字符串、空数组或空对象。\n- story_arcs 用于描述全书主弧线与阶段推进。\n- volume_plan_hints 用于提示后续卷级拆分，但不要写成完整卷纲。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n总纲目标参数：{outline_targets_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "rough_volume_outline": "你是小说粗卷纲助手。请基于总纲和项目目标，生成全书所有卷的粗略纲要。必须按卷分段输出，structured 才是主体，content 只保留整卷摘要。\n\n要求：\n- 只输出 JSON。\n- 顶层必须包含 content、overview、key_facts、constraints、open_questions、best_for_reason、structured。\n- structured 必须包含 volumes。\n- volumes 是数组，每个元素必须包含 volume_index、title、summary、goal、main_conflict、ending_hook、target_chapter_count、target_words。\n- 每个卷条目都要短，title 简短，summary 1~2 句，goal 一句话，main_conflict 一句话，ending_hook 一句话。\n- 不要展开成完整卷纲，不要写成章节细纲。\n- content 只能写全书卷级规划摘要，不能重复完整 volumes 列表。\n- 如果某项为空，输出空字符串或空数组，不要省略键。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n总纲目标参数：{outline_targets_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "volume_outline": "你是小说卷纲助手。请基于总纲摘要和当前卷对应的粗卷纲，生成当前卷的完整卷纲。structured 才是主体，content 只保留当前卷摘要。\n\n要求：\n- 只输出 JSON。\n- 顶层必须包含 content、overview、key_facts、constraints、open_questions、best_for_reason、structured。\n- structured 必须包含 volume_index、title、summary、goal、main_conflict、ending_hook、target_chapter_count、target_words、arc_segments。\n- arc_segments 用于描述卷内整体结构和阶段推进，不要展开成每章的细纲。\n- chapter_briefs 可以只保留短条目，供后续粗章纲参考。\n- content 只是当前卷摘要，不能把 arc_segments 和 chapter_briefs 重复写一遍。\n- 如果某项为空，输出空字符串或空数组，不要省略键。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置粗卷纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "rough_chapter_plan": "你是小说粗章纲助手。请基于当前卷的完整卷纲，默认一次性生成整卷全部章节的粗略章节计划。structured 才是主体，content 只保留整卷摘要，不要重复章节列表。\n\n要求：\n- 只输出 JSON。\n- 顶层必须包含 content、overview、key_facts、constraints、open_questions、best_for_reason、structured。\n- structured 必须包含 volume_index、total_target_chapters、chapters。\n- chapters 必须覆盖整卷全部章节，chapter_index 连续，不得跳号、漏章、重复。\n- 每章只保留紧凑骨架信息：title、summary、chapter_type、pov_character、main_event、conflict、hook、target_words。\n- title 必须简短。summary 只允许 1~2 句。main_event、conflict、hook 都必须是一句话。\n- 不要写 scene 级展开，不要写长段分析，不要加冗余说明。\n- content 只写整卷章节骨架摘要，不得复制章节列表。\n- 如果某项为空，输出空字符串或空数组，不要省略键。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置卷纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "chapter_plan": "你是章节计划助手。请基于当前卷的粗章纲，生成当前章的完整章节计划。structured 才是主体，content 只保留当前章摘要。\n\n要求：\n- 只输出 JSON。\n- 顶层必须包含 content、overview、key_facts、constraints、open_questions、best_for_reason、structured。\n- structured 必须包含 volume_index、chapter_index、title、summary、chapter_type、pov_character、main_event、conflict、hook、target_words、min_words、characters、introduced_characters、scene_summaries、continuity_notes、writing_notes。\n- 这一阶段可以展开详细场景拆解、细节伏笔和写作提示，但这些内容必须放在 structured 里。\n- content 只是当前章的简短摘要，不要重复 scene_summaries 和 writing_notes。\n- 如果某项为空，输出空字符串或空数组，不要省略键。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置粗章纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "chapter": "你是章节写作助手。请生成章节正文草稿，保证节奏、冲突与场景推进，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "revision": "你是修订助手。请在保留核心内容的前提下，重写并优化表达、结构与一致性，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "consistency": "你是一致性检查助手。请指出设定冲突、时间线冲突与逻辑漏洞，并给出修复建议，同时同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "memory": "你是记忆整理助手。请抽取稳定设定、未决问题与后续写作提醒，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "field_completion": "你是小说参数补全助手。请根据字段上下文中的关键字段信息、同阶段表单和直接上游产物，补全或优化当前字段内容。\n\n要求：\n- 只输出可直接填入表单的内容，不要解释。\n- 字段类型为数字时，只输出数字。\n- 字段类型为复选框时，只输出 true 或 false。\n- 其他字段尽量简洁，优先输出可执行、可粘贴的内容。\n- 不要重复当前字段已经给出的内容；优先利用关键字段信息决定答案。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n步骤：{step_label}\n步骤说明：{step_description}\n字段：{field_label} ({field_type})\n字段提示：{field_placeholder}\n当前值：{current_value}\n字段上下文：{field_context_json}\n关键字段上下文：{reference_fields_json}\n同阶段表单（当前字段已移除）：{step_payload_json}\n直接上游步骤：{direct_dependency_steps_json}\n直接上游产物：{direct_dependency_artifacts_json}\n项目输入：{input_json}\n\n补全结果：",
    }

    def __init__(self, prompts_dir: str | Path):
        self.prompts_dir = Path(prompts_dir)

    def load(self, template_name: str) -> str:
        file_path = self.prompts_dir / f"{template_name}.md"
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        if template_name not in self.DEFAULT_TEMPLATES:
            raise FileNotFoundError(f"missing prompt template: {template_name}")
        return self.DEFAULT_TEMPLATES[template_name]


def _extract_prompt_int(prompt: str, key: str, default: int) -> int:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*(-?\d+)', prompt)
    if match is None:
        return default
    try:
        return int(match.group(1))
    except ValueError:
        return default


def _mock_planning_payload(artifact_key: str, prompt: str) -> dict[str, Any]:
    total_words = _extract_prompt_int(prompt, "target_words", 0)
    volume_count = max(_extract_prompt_int(prompt, "volume_count", 1), 1)
    chapters_per_volume = max(_extract_prompt_int(prompt, "chapters_per_volume", 12), 1)
    volume_index = max(_extract_prompt_int(prompt, "volume_index", 1), 1)
    target_chapter_count = max(_extract_prompt_int(prompt, "target_chapter_count", chapters_per_volume), 1)
    chapter_index = max(_extract_prompt_int(prompt, "chapter_index", 1), 1)

    base_payload: dict[str, Any] = {
        "content": "基于当前输入生成的结构化规划摘要。",
        "overview": "结构化规划摘要，供下游步骤读取主体字段。",
        "key_facts": [f"{artifact_key} 的占位关键事实"],
        "constraints": ["占位约束，后续由真实模型细化。"],
        "open_questions": ["占位未解决问题，后续由真实模型细化。"],
        "best_for_reason": "这份内容包含摘要和结构化字段，便于下游步骤直接继承。",
        "structured": {},
    }

    if artifact_key == "outline":
        base_payload["content"] = "全书总纲摘要，概括主线、阶段推进和卷级拆分方向。"
        base_payload["structured"] = {
            "story_arcs": [
                {
                    "arc_index": 1,
                    "title": "主线推进",
                    "summary": "围绕核心冲突逐步升级，推动主角完成阶段性成长。",
                }
            ],
            "global_goals": ["建立故事主线", "明确阶段目标", "为卷级拆分提供统一方向"],
            "main_conflicts": ["主角目标与现实阻力的冲突", "阶段推进与代价之间的冲突"],
            "ending_direction": "在保持全书方向一致的前提下，为卷级展开留下清晰入口。",
            "volume_plan_hints": [
                {
                    "volume_index": index,
                    "hint": f"第{index}卷围绕一个阶段目标展开，建议约 {chapters_per_volume} 章。",
                }
                for index in range(1, volume_count + 1)
            ],
        }
        return base_payload

    if artifact_key == "rough_volume_outline":
        base_payload["content"] = "全书粗卷纲摘要，概括各卷的阶段目标与卷级结构。"
        base_payload["structured"] = {
            "volumes": [
                {
                    "volume_index": index,
                    "title": f"第{index}卷：阶段{index}",
                    "summary": f"第{index}卷的阶段性推进摘要。",
                    "goal": f"完成第{index}卷的核心推进。",
                    "main_conflict": f"第{index}卷的卷级冲突。",
                    "ending_hook": f"第{index}卷的收束钩子。",
                    "target_chapter_count": chapters_per_volume,
                    "target_words": max(total_words // volume_count, chapters_per_volume * 1500) if total_words else chapters_per_volume * 1500,
                }
                for index in range(1, volume_count + 1)
            ]
        }
        return base_payload

    if artifact_key == "volume_outline":
        base_payload["content"] = f"第{volume_index}卷摘要，概括卷内推进、冲突和钩子。"
        base_payload["structured"] = {
            "volume_index": volume_index,
            "title": f"第{volume_index}卷：阶段{volume_index}",
            "summary": f"第{volume_index}卷的完整卷纲摘要。",
            "goal": f"完成第{volume_index}卷的卷级目标。",
            "main_conflict": f"第{volume_index}卷的主要冲突。",
            "ending_hook": f"第{volume_index}卷的卷尾钩子。",
            "target_chapter_count": target_chapter_count,
            "target_words": max(total_words // volume_count, target_chapter_count * 1500) if total_words else target_chapter_count * 1500,
            "arc_segments": [
                {"segment_index": 1, "summary": "开局建立卷内局势。"},
                {"segment_index": 2, "summary": "中段推动冲突升级。"},
                {"segment_index": 3, "summary": "结尾收束并引出下卷。"},
            ],
        }
        return base_payload

    if artifact_key == "rough_chapter_plan":
        base_payload["content"] = f"第{volume_index}卷章节骨架摘要，共 {target_chapter_count} 章。"
        base_payload["structured"] = {
            "volume_index": volume_index,
            "total_target_chapters": target_chapter_count,
            "chapters": [
                {
                    "chapter_index": index,
                    "title": f"第{index}章：章节{index}",
                    "summary": f"第{index}章的简短摘要。",
                    "chapter_type": "主线推进章" if index % 3 else "冲突章",
                    "pov_character": "",
                    "main_event": f"第{index}章的核心事件。",
                    "conflict": f"第{index}章的主要冲突。",
                    "hook": f"第{index}章的收尾钩子。",
                    "target_words": max((total_words // volume_count) // target_chapter_count, 2000) if total_words else 3000,
                }
                for index in range(1, target_chapter_count + 1)
            ],
        }
        return base_payload

    if artifact_key == "chapter_plan":
        base_payload["content"] = f"第{volume_index}卷第{chapter_index}章摘要，概括本章目标与推进。"
        base_payload["structured"] = {
            "volume_index": volume_index,
            "chapter_index": chapter_index,
            "title": f"第{chapter_index}章：章节{chapter_index}",
            "summary": f"第{chapter_index}章的完整章节计划摘要。",
            "chapter_type": "主线推进章",
            "pov_character": "",
            "main_event": f"第{chapter_index}章的核心推进事件。",
            "conflict": f"第{chapter_index}章的主要冲突。",
            "hook": f"第{chapter_index}章的结尾钩子。",
            "target_words": max(_extract_prompt_int(prompt, "target_words", 3000), 1000),
            "min_words": max(_extract_prompt_int(prompt, "min_words", 2000), 800),
            "characters": [],
            "introduced_characters": [],
            "scene_summaries": [],
            "continuity_notes": [],
            "writing_notes": [],
        }
        return base_payload

    return base_payload


class FileAuditSink(AuditSink):
    def __init__(self, audit_log_path: str | Path):
        self.audit_log_path = Path(audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: AuditEvent) -> None:
        with self.audit_log_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(event.model_dump_json() + "\n")


class MemoryTaskStore(TaskStore):
    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def create(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return None if task is None else task.model_copy(deep=True)

    def list(self, project_id: str | None = None) -> list[TaskRecord]:
        with self._lock:
            tasks = list(self._tasks.values())
        if project_id is None:
            return [task.model_copy(deep=True) for task in tasks]
        return [task.model_copy(deep=True) for task in tasks if task.project_id == project_id]

    def update(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def delete(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def delete_by_project(self, project_id: str) -> int:
        with self._lock:
            task_ids = [task_id for task_id, task in self._tasks.items() if task.project_id == project_id]
            for task_id in task_ids:
                self._tasks.pop(task_id, None)
        return len(task_ids)


class MockLLMProvider(LLMProvider):
    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1200,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        metadata = metadata or {}
        title = metadata.get("artifact_title", "草稿")
        artifact_key = metadata.get("artifact_key", "draft")
        head = prompt[:800].strip()
        if "只输出 JSON" in prompt or "JSON：" in prompt:
            payload = _mock_planning_payload(artifact_key, prompt)
            payload["content"] = payload.get("content") or f"基于当前输入生成的 {title} 占位摘要。"
            payload["overview"] = payload.get("overview") or f"{title} 的占位结构化摘要。"
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return (
            f"# {title}\n\n"
            f"- artifact_key: {artifact_key}\n"
            f"- temperature: {temperature}\n"
            f"- max_tokens: {max_tokens}\n\n"
            f"## system\n{system_prompt.strip() or 'N/A'}\n\n"
            f"## prompt\n{head}\n\n"
            f"## draft\n基于当前输入生成的占位草稿。后续可接入真实 LLM 提升质量。"
        )


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1200,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "你是一个小说写作助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        if not raw.strip():
            raise RuntimeError("LLM request returned an empty response body")
        try:
            data = json.loads(raw)
        except JSONDecodeError as exc:
            preview = raw.strip().replace("\n", " ")[:500]
            raise RuntimeError(f"LLM request returned invalid JSON: {preview or '<empty>'}") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response JSON is missing choices[0].message.content") from exc
        if content is None:
            raise RuntimeError("LLM response content is empty")
        return str(content)
