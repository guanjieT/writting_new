from __future__ import annotations

import json
import os
import re
from json import JSONDecodeError
import threading
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import uuid4

from .domain import AuditEvent, AuditSink, LLMProvider, NovelProject, ProjectRepository, PromptStore, TaskRecord, TaskStore, TaskStatus, utc_now


def _safe_key(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not value or any(character not in allowed for character in value):
        raise ValueError(f"unsafe key: {value!r}")
    return value


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


class FileProjectRepository(ProjectRepository):
    def __init__(self, projects_dir: str | Path):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, project_id: str) -> Path:
        return self.projects_dir / f"{_safe_key(project_id)}.json"

    def list(self) -> list[NovelProject]:
        with self._lock:
            items: list[NovelProject] = []
            for path in sorted(self.projects_dir.glob("*.json")):
                items.append(NovelProject.model_validate_json(path.read_text(encoding="utf-8")))
            return items

    def get(self, project_id: str) -> NovelProject | None:
        with self._lock:
            path = self._path(project_id)
            if not path.exists():
                return None
            return NovelProject.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, project: NovelProject) -> NovelProject:
        with self._lock:
            path = self._path(project.project_id)
            _atomic_write_text(path, project.model_dump_json(indent=2))
            return project

    def delete(self, project_id: str) -> NovelProject | None:
        with self._lock:
            path = self._path(project_id)
            if not path.exists():
                return None
            project = NovelProject.model_validate_json(path.read_text(encoding="utf-8"))
            path.unlink()
            return project


class FilePromptStore(PromptStore):
    DEFAULT_TEMPLATES: dict[str, str] = {
        "requirements": "[请使用 prompts/requirements.md - 此文件仅为 fallback]",
        "story_bible": "[请使用 prompts/story_bible.md - 此文件仅为 fallback]",
        "characters": "[请使用 prompts/characters.md - 此文件仅为 fallback]",
        "outline": "[请使用 prompts/outline.md - 此文件仅为 fallback]",
        "rough_volume_outline": "[请使用 prompts/rough_volume_outline.md - 此文件仅为 fallback]",
        "volume_outline": "[请使用 prompts/volume_outline.md - 此文件仅为 fallback]",
        "rough_chapter_plan": "[请使用 prompts/rough_chapter_plan.md - 此文件仅为 fallback]",
        "chapter_plan": "[请使用 prompts/chapter_plan.md - 此文件仅为 fallback]",
        "chapter": (
            "你是章节写作助手。请严格承接当前章节计划，把它写成可直接阅读的小说正文。\n\n"
            "要求：\n"
            "- 只输出 JSON。\n"
            "- content 必须是完整正文，不要写提纲、摘要或说明。\n"
            "- 必须优先承接“当前章节计划”，不要改写本章目标、场景顺序或关键约束。\n"
            "- 正文长度至少接近 target_words_85，宁可略长，不可明显偏短。\n\n"
            "项目：{project_summary}\n"
            "项目简报：{project_brief_json}\n"
            "当前章节计划：{parent_artifact_json}\n"
            "当前章节计划结构化重点：{chapter_plan_focus_json}\n"
            "当前上下文：{context_json}\n"
            "已有产物摘要：{artifacts_json}\n"
            "最低正文长度参考：{target_words_85}\n\n"
            "JSON："
        ),
        "revision": "[请使用 prompts/revision.md - 此文件仅为 fallback]",
        "consistency": "[请使用 prompts/consistency.md - 此文件仅为 fallback]",
        "memory": "[请使用 prompts/memory.md - 此文件仅为 fallback]",
        "field_completion": "[请使用 prompts/field_completion.md - 此文件仅为 fallback]",
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

    def missing_templates(self, template_names: list[str]) -> list[str]:
        return [
            template_name
            for template_name in template_names
            if not (self.prompts_dir / f"{template_name}.md").exists()
        ]

    def validate_required(self, template_names: list[str]) -> None:
        missing = self.missing_templates(template_names)
        if missing:
            formatted = ", ".join(f"{template}.md" for template in missing)
            raise FileNotFoundError(f"missing required prompt templates in {self.prompts_dir}: {formatted}")


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


class FileTaskStore(TaskStore):
    def __init__(self, tasks_dir: str | Path):
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._mark_interrupted_tasks()

    def _path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{_safe_key(task_id)}.json"

    def _read_path(self, path: Path) -> TaskRecord:
        return TaskRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def _write(self, task: TaskRecord) -> TaskRecord:
        _atomic_write_text(self._path(task.task_id), task.model_dump_json(indent=2))
        return task

    def _mark_interrupted_tasks(self) -> None:
        with self._lock:
            for path in sorted(self.tasks_dir.glob("*.json")):
                task = self._read_path(path)
                if task.status not in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                    continue
                task.status = TaskStatus.FAILED
                task.error = task.error or "task interrupted by service restart"
                task.finished_at = task.finished_at or utc_now()
                self._write(task)

    def create(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            return self._write(task).model_copy(deep=True)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            path = self._path(task_id)
            if not path.exists():
                return None
            return self._read_path(path).model_copy(deep=True)

    def list(self, project_id: str | None = None) -> list[TaskRecord]:
        with self._lock:
            tasks = [self._read_path(path) for path in sorted(self.tasks_dir.glob("*.json"))]
        if project_id is not None:
            tasks = [task for task in tasks if task.project_id == project_id]
        return [task.model_copy(deep=True) for task in tasks]

    def update(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            return self._write(task).model_copy(deep=True)

    def delete(self, task_id: str) -> None:
        with self._lock:
            path = self._path(task_id)
            if path.exists():
                path.unlink()

    def delete_by_project(self, project_id: str) -> int:
        with self._lock:
            paths = [
                path
                for path in sorted(self.tasks_dir.glob("*.json"))
                if self._read_path(path).project_id == project_id
            ]
            for path in paths:
                path.unlink()
            return len(paths)


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
