from __future__ import annotations

import json
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
        "outline": "你是小说总纲助手。请先生成全书总纲，只覆盖全书级别的目标、主线节奏、阶段推进和全局约束，不要展开成卷纲或章节计划。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n总纲目标参数：{outline_targets_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "rough_volume_outline": "你是小说粗卷纲助手。请基于总纲和项目目标，生成全书所有卷的粗略纲要，不要拆成单卷输出。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- 这一阶段只输出卷级粗纲，重点是每卷的目标、冲突、卷尾钩子和卷间节奏，不要写成完整卷纲。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n总纲目标参数：{outline_targets_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "volume_outline": "你是小说卷纲助手。请基于总纲摘要和当前卷对应的粗卷纲，直接在粗卷纲基础上修改、扩写、细化，生成当前卷的完整卷纲。不要从头重写，也不要脱离粗卷纲另起一套结构。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- chapter_briefs 可以保留为清晰可编辑的列表，用于后续粗章纲参考。\n- 必须保留粗卷纲中的卷序、卷目标、卷尾钩子和主要冲突框架，并在此基础上补足细节。\n- 如果粗卷纲已有章节安排，优先沿用并细化，不要改成全新章节结构。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置粗卷纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "rough_chapter_plan": "你是小说粗章纲助手。请基于当前卷的完整卷纲，直接在卷纲基础上拆出该卷所有章节的粗略章节计划，不要从头重新设计章节结构。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- 这一阶段只输出当前卷所有章节的粗略安排，重点是每章的目标、冲突、转场和节奏，不要写成可直接正文。\n- 必须继承卷纲中的章节顺序、章节目标和关键转折，并在此基础上做粗化拆分。\n- 如果卷纲已有章节标题或章节骨架，优先沿用，不要重新命名成另一套章节。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置卷纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "chapter_plan": "你是章节计划助手。请基于当前卷的粗章纲，直接在粗章纲基础上修改、扩写、细化，生成当前章的完整章节计划。不要从头重写，也不要脱离粗章纲另起一套章节安排。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- 这一阶段只覆盖当前章，不要把别的章节内容混进来。\n- 必须保留粗章纲中的当前章定位、目标、冲突、转场和节奏，并在此基础上补足细节。\n- 如果粗章纲里已经有当前章的骨架，优先沿用并细化，不要改成新的章节结构。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n前置粗章纲摘要：{parent_artifact_json}\n步骤输入：{step_payload_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "chapter": "你是章节写作助手。请生成章节正文草稿，保证节奏、冲突与场景推进，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "revision": "你是修订助手。请在保留核心内容的前提下，重写并优化表达、结构与一致性，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "consistency": "你是一致性检查助手。请指出设定冲突、时间线冲突与逻辑漏洞，并给出修复建议，同时同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "memory": "你是记忆整理助手。请抽取稳定设定、未决问题与后续写作提醒，并同步输出结构化字段。\n\n要求：\n- 只输出 JSON。\n- content: 纯文本字符串正文，不要放对象或数组。\n- overview: 一两句概括这一阶段产物的作用。\n- key_facts: 事实性条目，适合给后续步骤继承。\n- constraints: 不能改的边界。\n- open_questions: 后续还要接着处理的点。\n- best_for_reason: 说明这份内容为什么适合给下游步骤使用。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n当前上下文：{context_json}\n已有产物摘要：{artifacts_json}\n\nJSON：",
        "field_completion": "你是小说参数补全助手。请根据项目、步骤和字段信息，直接补全或优化当前字段内容。\n\n要求：\n- 只输出可直接填入表单的内容，不要解释。\n- 字段类型为数字时，只输出数字。\n- 字段类型为复选框时，只输出 true 或 false。\n- 其他字段尽量简洁，优先输出可执行、可粘贴的内容。\n- 优先参考同一阶段的约束字段，再参考直接上游产物；不要把无关历史信息混进答案。\n\n项目：{project_summary}\n项目简报：{project_brief_json}\n步骤：{step_label}\n步骤说明：{step_description}\n字段：{field_label} ({field_type})\n字段提示：{field_placeholder}\n当前值：{current_value}\n字段上下文：{field_context_json}\n同阶段表单：{step_payload_json}\n直接上游步骤：{direct_dependency_steps_json}\n直接上游产物：{direct_dependency_artifacts_json}\n项目输入：{input_json}\n\n补全结果：",
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
            payload = {
                "content": f"基于当前输入生成的 {title} 占位草稿。",
                "overview": f"{title} 的占位结构化摘要。",
                "key_facts": [f"{artifact_key} 的占位关键事实"],
                "constraints": ["占位约束，后续由真实模型细化。"],
                "open_questions": ["占位未解决问题，后续由真实模型细化。"],
                "best_for_reason": "这份内容包含正文与结构化字段，便于下游步骤直接继承。",
            }
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
