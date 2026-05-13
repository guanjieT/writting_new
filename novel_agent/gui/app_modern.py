"""Final CustomTkinter GUI for Novel Agent.

Default entry for ``python -m novel_agent.gui``.  It keeps the existing domain,
service, orchestrator and task layers, but replaces the visual shell with a
modern CustomTkinter interface.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
from typing import Any

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "缺少 CustomTkinter。请先安装：\n\n"
        "    pip install customtkinter\n"
    ) from exc

from novel_agent.config import load_config
from novel_agent.container import build_container
from novel_agent.domain import ProjectInput
from novel_agent.services import task_scope_from_payload

from .scope_utils import (
    build_base_artifact_payload,
    get_artifact_for_step,
    get_chapter_entry_options,
    get_current_artifact_options,
    get_field_display_value,
    get_field_select_options,
    get_step_readiness_message,
    get_step_status,
    get_volume_entry_options,
    is_unlocked,
    selection_for_step,
)
from .state import AppShared
from .step_fields import (
    FIELD_CHECKBOX,
    FIELD_LIST,
    FIELD_NUMBER,
    FIELD_SELECT,
    FIELD_TEXTAREA,
    PAGE_STEP_GROUPS,
    REVIEW_GROUPS,
    get_step_def,
    get_step_label,
)
from .task_monitor import TaskMonitor

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

FONT = "Microsoft YaHei UI"
C = {
    "shell": "#0b1020",
    "shell2": "#111827",
    "shell3": "#1f2937",
    "page": "#f8fafc",
    "card": "#ffffff",
    "soft": "#f1f5f9",
    "line": "#e2e8f0",
    "text": "#0f172a",
    "muted": "#64748b",
    "light": "#e5e7eb",
    "white": "#ffffff",
    "primary": "#7c3aed",
    "primary_hover": "#6d28d9",
    "blue": "#2563eb",
    "blue_hover": "#1d4ed8",
    "green": "#10b981",
    "amber": "#f59e0b",
    "red": "#ef4444",
    "red_hover": "#dc2626",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _dump(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _pid(project: Any) -> str:
    return str(project.get("project_id", "") if isinstance(project, dict) else getattr(project, "project_id", ""))


def _pinput(project: Any) -> dict:
    if isinstance(project, dict):
        return project.get("input", {}) or {}
    data = getattr(project, "input", None)
    return data.model_dump(mode="json") if hasattr(data, "model_dump") else _dump(data)


def _pstatus(project: Any) -> str:
    value = project.get("status", "") if isinstance(project, dict) else getattr(project, "status", "")
    return str(value.value if hasattr(value, "value") else value)


def _lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return "" if value is None else str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


class Scroll(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(
            master,
            fg_color="transparent",
            scrollbar_button_color="#cbd5e1",
            scrollbar_button_hover_color="#94a3b8",
            **kwargs,
        )


class Card(ctk.CTkFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=C["card"], corner_radius=22, border_width=1, border_color=C["line"], **kwargs)


class Metric(Card):
    def __init__(self, master: Any, label: str, value: str, color: str) -> None:
        super().__init__(master)
        ctk.CTkLabel(self, text=value, text_color=color, font=(FONT, 24, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(self, text=label, text_color=C["muted"], font=(FONT, 12)).pack(anchor="w", padx=18, pady=(0, 14))


# ---------------------------------------------------------------------------
# Main app shell
# ---------------------------------------------------------------------------


class ModernApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Novel Agent — 小说创作工作台")
        self.geometry("1500x940")
        self.minsize(1200, 720)
        self.configure(fg_color=C["page"])

        config = load_config()
        self.container = build_container(config)
        self.shared = AppShared(container=self.container, task_monitor=TaskMonitor(self, self.container.task_service))

        self._current = "project"
        self._views: dict[str, Any] = {}
        self._volume_options: list[dict] = []
        self._chapter_options: list[dict] = []
        self._build_shell()
        self.switch("project")

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.side = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=C["shell"])
        self.side.grid(row=0, column=0, sticky="nsew")
        self.side.grid_propagate(False)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=C["page"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_header()

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._views = {
            "project": ProjectView(self.content, self),
            "workflow": WorkflowView(self.content, self),
            "review": ReviewView(self.content, self),
        }

    def _build_sidebar(self) -> None:
        ctk.CTkLabel(self.side, text="✦ Novel Agent", font=(FONT, 25, "bold"), text_color=C["white"]).pack(anchor="w", padx=24, pady=(28, 2))
        ctk.CTkLabel(self.side, text="AI fiction creation studio", font=(FONT, 13), text_color="#94a3b8").pack(anchor="w", padx=26, pady=(0, 22))

        pcard = ctk.CTkFrame(self.side, fg_color=C["shell2"], corner_radius=22)
        pcard.pack(fill="x", padx=18, pady=(0, 22))
        ctk.CTkLabel(pcard, text="当前项目", font=(FONT, 12), text_color="#94a3b8").pack(anchor="w", padx=18, pady=(16, 0))
        self.project_title = ctk.CTkLabel(pcard, text="未选择", font=(FONT, 17, "bold"), text_color=C["white"], wraplength=230, justify="left")
        self.project_title.pack(anchor="w", padx=18, pady=(4, 2))
        self.project_meta = ctk.CTkLabel(pcard, text="先创建或选择作品", font=(FONT, 12), text_color="#94a3b8", wraplength=230, justify="left")
        self.project_meta.pack(anchor="w", padx=18, pady=(0, 16))

        ctk.CTkLabel(self.side, text="导航", font=(FONT, 12, "bold"), text_color="#94a3b8").pack(anchor="w", padx=24, pady=(0, 8))
        self.nav: dict[str, ctk.CTkButton] = {}
        for key, label in [("project", "项目中心"), ("workflow", "创作工作台"), ("review", "审查面板")]:
            btn = ctk.CTkButton(
                self.side,
                text=label,
                height=46,
                corner_radius=15,
                anchor="w",
                fg_color="transparent",
                hover_color=C["shell2"],
                text_color="#dbeafe",
                font=(FONT, 14, "bold"),
                command=lambda k=key: self.switch(k),
            )
            btn.pack(fill="x", padx=18, pady=4)
            self.nav[key] = btn

        scope = ctk.CTkFrame(self.side, fg_color=C["shell2"], corner_radius=20)
        scope.pack(fill="x", padx=18, pady=(22, 0))
        ctk.CTkLabel(scope, text="创作范围", font=(FONT, 14, "bold"), text_color=C["white"]).pack(anchor="w", padx=16, pady=(15, 8))
        self.volume_menu = ctk.CTkOptionMenu(scope, values=["第 1 卷"], fg_color=C["shell3"], button_color=C["primary"], corner_radius=12, command=lambda _v: self._change_scope())
        self.volume_menu.pack(fill="x", padx=14, pady=5)
        self.chapter_menu = ctk.CTkOptionMenu(scope, values=["第 1 章"], fg_color=C["shell3"], button_color=C["primary"], corner_radius=12, command=lambda _v: self._change_scope())
        self.chapter_menu.pack(fill="x", padx=14, pady=(5, 16))

        bottom = ctk.CTkFrame(self.side, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=24, pady=24)
        ctk.CTkLabel(bottom, text="任务状态", font=(FONT, 12, "bold"), text_color="#94a3b8").pack(anchor="w")
        self.task_status = ctk.CTkLabel(bottom, text="● 无运行任务", font=(FONT, 12), text_color="#94a3b8")
        self.task_status.pack(anchor="w", pady=(5, 0))

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self.main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 18))
        head.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(head, text="项目中心", font=(FONT, 29, "bold"), text_color=C["text"])
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_hint = ctk.CTkLabel(head, text="创建、选择并维护作品蓝图", font=(FONT, 13), text_color=C["muted"])
        self.page_hint.grid(row=1, column=0, sticky="w", pady=(2, 0))
        ctk.CTkButton(head, text="刷新", width=96, height=38, corner_radius=13, fg_color=C["shell3"], hover_color=C["shell2"], command=self.refresh).grid(row=0, column=1, rowspan=2, sticky="e")

    def switch(self, name: str) -> None:
        if name in ("workflow", "review") and not self.shared.current_project_id:
            messagebox.showwarning("未选择项目", "请先在项目中心选择或创建一个项目。")
            name = "project"
        for key, view in self._views.items():
            if key == name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()
        self._current = name
        meta = {
            "project": ("项目中心", "创建、选择并维护作品蓝图"),
            "workflow": ("创作工作台", "按依赖顺序推进设定、纲要、章节和审查"),
            "review": ("审查面板", "集中查看进度、任务历史和质量阻塞项"),
        }
        self.page_title.configure(text=meta[name][0])
        self.page_hint.configure(text=meta[name][1])
        for key, btn in self.nav.items():
            btn.configure(
                fg_color=C["primary"] if key == name else "transparent",
                hover_color=C["primary_hover"] if key == name else C["shell2"],
                text_color=C["white"] if key == name else "#dbeafe",
            )
        self.refresh()

    def refresh(self) -> None:
        self._refresh_scope()
        self._refresh_badge()
        view = self._views.get(self._current)
        if view and hasattr(view, "refresh"):
            view.refresh()

    def _refresh_badge(self) -> None:
        project = self.shared.project()
        if project:
            pi = project.get("input", {}) or {}
            self.project_title.configure(text=pi.get("title", "未命名"))
            self.project_meta.configure(text=f"{pi.get('genre', '')}\n状态：{project.get('status', '')}")
        else:
            self.project_title.configure(text="未选择")
            self.project_meta.configure(text="先创建或选择作品")
        active = self.shared.task_monitor.active_count
        self.task_status.configure(text=f"● 运行中：{active} 个任务" if active else "● 无运行任务")

    def _refresh_scope(self) -> None:
        snapshot = self.shared.current_snapshot
        self._volume_options = get_volume_entry_options(snapshot) or [{"value": "1", "label": "第 1 卷"}]
        self.volume_menu.configure(values=[o["label"] for o in self._volume_options])
        current_v = str(self.shared.scope.volume_index or 1)
        vol = next((o for o in self._volume_options if o["value"] == current_v), self._volume_options[0])
        self.volume_menu.set(vol["label"])
        self._chapter_options = get_chapter_entry_options(snapshot, _safe_int(vol["value"], 1)) or [{"value": "1", "label": "第 1 章"}]
        self.chapter_menu.configure(values=[o["label"] for o in self._chapter_options])
        current_c = str(self.shared.scope.chapter_index or 1)
        ch = next((o for o in self._chapter_options if o["value"] == current_c), self._chapter_options[0])
        self.chapter_menu.set(ch["label"])

    def _change_scope(self) -> None:
        for opt in self._volume_options:
            if opt["label"] == self.volume_menu.get():
                self.shared.scope.volume_index = _safe_int(opt["value"], 1)
                break
        for opt in self._chapter_options:
            if opt["label"] == self.chapter_menu.get():
                self.shared.scope.chapter_index = _safe_int(opt["value"], 1)
                break
        if self._current in ("workflow", "review"):
            self.refresh()


# ---------------------------------------------------------------------------
# Project center
# ---------------------------------------------------------------------------


class ProjectView(ctk.CTkFrame):
    def __init__(self, master: Any, app: ModernApp) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self.widgets: dict[str, tuple[str, Any]] = {}
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        left = Card(self, width=370)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="作品库", font=(FONT, 23, "bold"), text_color=C["text"]).pack(anchor="w", padx=22, pady=(22, 0))
        ctk.CTkLabel(left, text="选择作品后进入生成工作流", font=(FONT, 13), text_color=C["muted"]).pack(anchor="w", padx=22, pady=(2, 16))

        self.metrics = ctk.CTkFrame(left, fg_color="transparent")
        self.metrics.pack(fill="x", padx=18, pady=(0, 12))
        self.metrics.grid_columnconfigure((0, 1), weight=1)
        self.project_list = Scroll(left)
        self.project_list.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        hero = ctk.CTkFrame(right, fg_color="#ede9fe", corner_radius=24)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ctk.CTkLabel(hero, text="作品蓝图", font=(FONT, 29, "bold"), text_color="#2e1065").pack(anchor="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(hero, text="先把题材、前提、规模和风格约束整理为统一源头，后续所有生成步骤都会基于这里。", font=(FONT, 14), text_color="#6b21a8", wraplength=850, justify="left").pack(anchor="w", padx=24, pady=(0, 22))

        self.form = Scroll(right)
        self.form.grid(row=1, column=0, sticky="nsew")
        self._build_form()

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.create_btn = ctk.CTkButton(actions, text="＋ 创建项目", height=43, corner_radius=15, fg_color=C["primary"], hover_color=C["primary_hover"], command=self._create)
        self.create_btn.pack(side="left")
        self.update_btn = ctk.CTkButton(actions, text="保存修改", height=43, corner_radius=15, fg_color=C["shell3"], hover_color=C["shell2"], state="disabled", command=self._update)
        self.update_btn.pack(side="left", padx=10)
        self.delete_btn = ctk.CTkButton(actions, text="删除", height=43, corner_radius=15, fg_color=C["red"], hover_color=C["red_hover"], state="disabled", command=self._delete)
        self.delete_btn.pack(side="left")
        self.open_btn = ctk.CTkButton(actions, text="进入创作工作台 →", height=43, corner_radius=15, fg_color=C["blue"], hover_color=C["blue_hover"], state="disabled", command=lambda: self.app.switch("workflow"))
        self.open_btn.pack(side="right")

    def _build_form(self) -> None:
        sections = [
            ("作品定位", [("title", "作品标题", "text", 0), ("genre", "作品类型", "text", 0), ("premise", "前提/核心构思", "area", 5), ("target_audience", "目标受众", "text", 0)]),
            ("规模与节奏", [("target_words", "目标总字数", "number", 0), ("target_volume_count", "目标卷数", "number", 0), ("target_chapters_per_volume", "每卷章节数", "number", 0)]),
            ("风格与约束", [("tone", "基调标签（一行一个）", "list", 4), ("style", "风格标签（一行一个）", "list", 4), ("outline_focus", "总纲关注点（一行一个）", "list", 4), ("core_requirements", "核心要求（一行一个）", "list", 4), ("forbidden_elements", "禁忌元素（一行一个）", "list", 4)]),
        ]
        for title, fields in sections:
            card = Card(self.form)
            card.pack(fill="x", padx=3, pady=(0, 14))
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=title, font=(FONT, 18, "bold"), text_color=C["text"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 10))
            for row, (key, label, kind, rows) in enumerate(fields, start=1):
                ctk.CTkLabel(card, text=label, font=(FONT, 13), text_color=C["muted"]).grid(row=row, column=0, sticky="nw", padx=(20, 18), pady=8)
                if kind in ("area", "list"):
                    w = ctk.CTkTextbox(card, height=max(rows, 3) * 30, corner_radius=13, fg_color=C["soft"], border_width=1, border_color=C["line"], text_color=C["text"])
                    w.grid(row=row, column=1, sticky="ew", padx=(0, 20), pady=8)
                else:
                    w = ctk.CTkEntry(card, height=41, corner_radius=13, fg_color=C["soft"], border_width=1, border_color=C["line"], text_color=C["text"])
                    w.grid(row=row, column=1, sticky="ew", padx=(0, 20), pady=8)
                self.widgets[key] = (kind, w)

    def _read(self) -> dict:
        payload: dict[str, Any] = {}
        for key, (kind, widget) in self.widgets.items():
            raw = widget.get("1.0", "end-1c") if kind in ("area", "list") else widget.get()
            if kind == "list":
                payload[key] = [x.strip() for x in raw.splitlines() if x.strip()]
            elif kind == "number":
                payload[key] = _safe_int(raw)
            else:
                payload[key] = raw
        return payload

    def _fill(self, data: dict) -> None:
        for key, (kind, widget) in self.widgets.items():
            value = _lines(data.get(key, ""))
            if kind in ("area", "list"):
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            else:
                widget.delete(0, "end")
                widget.insert(0, value)

    def refresh(self) -> None:
        try:
            projects = self.shared.container.orchestrator.list_projects()
        except Exception:
            projects = []

        for child in self.metrics.winfo_children():
            child.destroy()
        Metric(self.metrics, "项目", str(len(projects)), C["primary"]).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        Metric(self.metrics, "当前", "已选" if self.shared.current_project_id else "未选", C["blue"]).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        for child in self.project_list.winfo_children():
            child.destroy()
        for project in projects:
            pid = _pid(project)
            pi = _pinput(project)
            selected = pid == self.shared.current_project_id
            btn = ctk.CTkButton(
                self.project_list,
                text=f"{pi.get('title', '未命名')}\n{pi.get('genre', '')} · {_pstatus(project)}",
                height=64,
                corner_radius=17,
                anchor="w",
                justify="left",
                fg_color=C["primary"] if selected else C["soft"],
                hover_color=C["primary_hover"] if selected else "#e2e8f0",
                text_color=C["white"] if selected else C["text"],
                font=(FONT, 13, "bold"),
                command=lambda p=pid: self._select(p),
            )
            btn.pack(fill="x", pady=6)

        if self.shared.current_project_id:
            self._load()
        else:
            self._fill({})
            for btn in (self.update_btn, self.delete_btn, self.open_btn):
                btn.configure(state="disabled")

    def _select(self, pid: str) -> None:
        self.shared.current_project_id = pid
        self._load()
        self.app.refresh()

    def _load(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            self.shared.current_snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
            self._fill((self.shared.current_snapshot.get("project", {}) or {}).get("input", {}) or {})
            for btn in (self.update_btn, self.delete_btn, self.open_btn):
                btn.configure(state="normal")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _create(self) -> None:
        payload = self._read()
        if not payload.get("title") or not payload.get("genre"):
            messagebox.showwarning("缺少信息", "作品标题和类型为必填项。")
            return
        try:
            project = self.shared.container.orchestrator.create_project(ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])}))
            self.shared.current_project_id = project.project_id
            self.app.refresh()
            messagebox.showinfo("成功", f"项目 '{project.input.title}' 创建成功。")
        except Exception as e:
            messagebox.showerror("创建失败", str(e))

    def _update(self) -> None:
        if not self.shared.current_project_id:
            return
        if not messagebox.askyesno("确认更新", "更新项目会清除已有产物和历史记录，确定继续？"):
            return
        try:
            payload = self._read()
            self.shared.container.orchestrator.update_project(self.shared.current_project_id, ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])}))
            self.app.refresh()
            messagebox.showinfo("成功", "项目已更新。")
        except Exception as e:
            messagebox.showerror("更新失败", str(e))

    def _delete(self) -> None:
        if not self.shared.current_project_id:
            return
        if not messagebox.askyesno("确认删除", "删除操作不可撤销，确定要删除此项目吗？"):
            return
        try:
            pid = self.shared.current_project_id
            self.shared.container.task_service.delete_project(pid)
            self.shared.container.project_service.delete(pid)
            self.shared.current_project_id = ""
            self.shared.current_snapshot = None
            self.shared.current_tasks = []
            self.app.refresh()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))


# ---------------------------------------------------------------------------
# Workflow page
# ---------------------------------------------------------------------------


class WorkflowView(ctk.CTkFrame):
    def __init__(self, master: Any, app: ModernApp) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self.step = ""
        self.fields: dict[str, tuple[str, Any, Any]] = {}
        self.running = False
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        self.nav = Card(self, width=285)
        self.nav.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.nav.grid_propagate(False)
        ctk.CTkLabel(self.nav, text="生成步骤", font=(FONT, 22, "bold"), text_color=C["text"]).pack(anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(self.nav, text="按依赖顺序推进", font=(FONT, 12), text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 12))
        self.step_list = Scroll(self.nav)
        self.step_list.pack(fill="both", expand=True, padx=14, pady=(0, 16))

        self.editor = Card(self)
        self.editor.grid(row=0, column=1, sticky="nsew", padx=(0, 18))
        self.editor.grid_columnconfigure(0, weight=1)
        self.editor.grid_rowconfigure(2, weight=1)
        self.step_title = ctk.CTkLabel(self.editor, text="选择步骤", font=(FONT, 24, "bold"), text_color=C["text"])
        self.step_title.grid(row=0, column=0, sticky="w", padx=22, pady=(20, 0))
        self.step_desc = ctk.CTkLabel(self.editor, text="", font=(FONT, 13), text_color=C["muted"], wraplength=570, justify="left")
        self.step_desc.grid(row=1, column=0, sticky="w", padx=22, pady=(2, 10))
        self.form = Scroll(self.editor)
        self.form.grid(row=2, column=0, sticky="nsew", padx=16)
        actions = ctk.CTkFrame(self.editor, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=16)
        self.run_btn = ctk.CTkButton(actions, text="生成", height=43, corner_radius=15, fg_color=C["primary"], hover_color=C["primary_hover"], state="disabled", command=self._run)
        self.run_btn.pack(side="left")
        self.del_btn = ctk.CTkButton(actions, text="删除产物", height=43, corner_radius=15, fg_color=C["red"], hover_color=C["red_hover"], state="disabled", command=self._delete_artifact)
        self.del_btn.pack(side="left", padx=10)
        self.status = ctk.CTkLabel(actions, text="", font=(FONT, 12), text_color=C["muted"])
        self.status.pack(side="right")

        self.viewer = Card(self)
        self.viewer.grid(row=0, column=2, sticky="nsew")
        self.viewer.grid_columnconfigure(0, weight=1)
        self.viewer.grid_rowconfigure(1, weight=1)

    def refresh(self) -> None:
        self._reload()
        self._draw_steps()
        if not self.step:
            self._select(PAGE_STEP_GROUPS["workflow"][0]["steps"][0])
        else:
            self._draw_step()

    def _reload(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            self.shared.current_snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
        except Exception:
            pass

    def _draw_steps(self) -> None:
        for child in self.step_list.winfo_children():
            child.destroy()
        for group in PAGE_STEP_GROUPS["workflow"]:
            ctk.CTkLabel(self.step_list, text=group["label"], font=(FONT, 12, "bold"), text_color=C["muted"]).pack(anchor="w", padx=8, pady=(12, 4))
            for step_key in group["steps"]:
                status = get_step_status(step_key, self.shared.current_snapshot, self.shared.current_tasks, selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index}))
                selected = step_key == self.step
                ctk.CTkButton(
                    self.step_list,
                    text=f"{get_step_label(step_key)}    {status.get('text', '')}",
                    height=39,
                    corner_radius=13,
                    anchor="w",
                    fg_color=C["primary"] if selected else C["soft"],
                    hover_color=C["primary_hover"] if selected else "#e2e8f0",
                    text_color=C["white"] if selected else C["text"],
                    font=(FONT, 12, "bold"),
                    command=lambda s=step_key: self._select(s),
                ).pack(fill="x", pady=3)

    def _select(self, step_key: str) -> None:
        self.step = step_key
        self.shared.current_step = step_key
        self._draw_steps()
        self._draw_step()

    def _draw_step(self) -> None:
        for child in self.form.winfo_children():
            child.destroy()
        self.fields = {}
        step_def = get_step_def(self.step)
        self.step_title.configure(text=step_def.label)
        self.step_desc.configure(text=step_def.description)
        selection = selection_for_step(self.step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        msg = get_step_readiness_message(self.step, self.shared.current_snapshot, selection)
        if msg:
            warn = ctk.CTkFrame(self.form, fg_color="#fef3c7", corner_radius=15)
            warn.pack(fill="x", padx=3, pady=(0, 12))
            ctk.CTkLabel(warn, text=msg, font=(FONT, 13), text_color="#92400e", wraplength=560, justify="left").pack(anchor="w", padx=15, pady=12)
        for field in step_def.fields:
            setattr(field, "step_key", self.step)
            value = get_field_display_value(field, self.shared.current_snapshot, selection)
            self._add_field(field, value, selection)
        ready = is_unlocked(self.step, self.shared.current_snapshot, selection)
        artifact = get_artifact_for_step(self.shared.current_snapshot, self.step, selection)
        self.run_btn.configure(state="normal" if ready and not self.running else "disabled")
        self.del_btn.configure(state="normal" if artifact else "disabled")
        self._draw_viewer(artifact)

    def _add_field(self, field: Any, value: Any, selection: dict) -> None:
        row = ctk.CTkFrame(self.form, fg_color=C["soft"], corner_radius=16)
        row.pack(fill="x", padx=3, pady=6)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=field.label, font=(FONT, 13, "bold"), text_color=C["text"]).grid(row=0, column=0, sticky="nw", padx=14, pady=12)
        key = field.key
        if field.field_type in (FIELD_TEXTAREA, FIELD_LIST):
            w = ctk.CTkTextbox(row, height=max(field.rows or 4, 3) * 30, corner_radius=13, fg_color=C["card"], border_width=1, border_color=C["line"], text_color=C["text"])
            w.insert("1.0", _lines(value))
            w.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=10)
            self.fields[key] = ("text", w, field)
        elif field.field_type == FIELD_CHECKBOX:
            var = tk.BooleanVar(value=bool(value))
            w = ctk.CTkCheckBox(row, text="", variable=var, fg_color=C["primary"])
            w.grid(row=0, column=1, sticky="w", padx=(0, 14), pady=10)
            self.fields[key] = ("bool", var, field)
        elif field.field_type == FIELD_SELECT:
            opts = get_field_select_options(field, self.shared.current_snapshot, selection)
            if not opts and field.option_source == "current_artifacts":
                opts = get_current_artifact_options(self.shared.current_snapshot, selection)
            labels = [o["label"] for o in opts] or [field.empty_label or "无可选项"]
            values = {o["label"]: o["value"] for o in opts}
            by_value = {str(o["value"]): o["label"] for o in opts}
            w = ctk.CTkOptionMenu(row, values=labels, fg_color=C["card"], button_color=C["primary"], text_color=C["text"], corner_radius=13)
            w.set(by_value.get(str(value), labels[0]))
            if field.disabled:
                w.configure(state="disabled")
            w.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=10)
            self.fields[key] = ("select", (w, values), field)
        else:
            w = ctk.CTkEntry(row, height=40, corner_radius=13, fg_color=C["card"], border_width=1, border_color=C["line"], text_color=C["text"])
            w.insert(0, _lines(value))
            w.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=10)
            self.fields[key] = ("entry", w, field)

    def _payload(self) -> dict:
        payload: dict[str, Any] = {}
        for key, (kind, target, field) in self.fields.items():
            if kind == "text":
                raw = target.get("1.0", "end-1c")
                payload[key] = [x.strip() for x in raw.splitlines() if x.strip()] if field.field_type == FIELD_LIST or getattr(field, "is_list", False) else raw
            elif kind == "bool":
                payload[key] = bool(target.get())
            elif kind == "select":
                menu, values = target
                payload[key] = values.get(menu.get(), menu.get())
            elif field.field_type == FIELD_NUMBER:
                payload[key] = _safe_int(target.get())
            else:
                payload[key] = target.get()
        return payload

    def _draw_viewer(self, artifact: dict | None) -> None:
        for child in self.viewer.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.viewer, text="产物预览", font=(FONT, 22, "bold"), text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        box = ctk.CTkTextbox(self.viewer, corner_radius=16, fg_color=C["soft"], border_width=1, border_color=C["line"], text_color=C["text"], wrap="word")
        box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        if not artifact:
            box.insert("1.0", "暂无产物。\n\n生成当前步骤后，这里会显示正文、摘要和关键元数据。")
        else:
            meta = artifact.get("metadata", {}) or {}
            content = artifact.get("content") or (meta.get("generated_payload", {}) or {}).get("content") or ""
            text = [f"标题：{artifact.get('title') or get_step_label(self.step)}", f"键：{artifact.get('key', '')}", "", str(content or "（无内容）")]
            if artifact.get("summary"):
                text.extend(["", "—— 摘要 ——", json.dumps(artifact.get("summary"), ensure_ascii=False, indent=2, default=str)])
            box.insert("1.0", "\n".join(text))
        box.configure(state="disabled")

    def _run(self) -> None:
        if not self.step or self.running:
            return
        selection = selection_for_step(self.step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        if not is_unlocked(self.step, self.shared.current_snapshot, selection):
            messagebox.showwarning("依赖未就绪", get_step_readiness_message(self.step, self.shared.current_snapshot, selection))
            return
        payload = self._payload()
        base = build_base_artifact_payload(self.step, self.shared.current_snapshot, selection)
        if base:
            payload["base_artifact"] = base
        self.running = True
        self.status.configure(text="生成中...")
        self.run_btn.configure(state="disabled")
        try:
            scope = task_scope_from_payload(self.step, payload)

            def job() -> Any:
                result = self.shared.container.orchestrator.dispatch(self.shared.current_project_id, self.step, payload)
                return result.model_dump(mode="json") if hasattr(result, "model_dump") else result

            task = self.shared.container.task_service.submit(self.shared.current_project_id, self.step, job, scope, payload)
            self.shared.task_monitor.start(task.task_id, on_complete=self._done, on_error=self._error)
        except Exception as e:
            self.running = False
            self.status.configure(text="")
            self.run_btn.configure(state="normal")
            messagebox.showerror("提交失败", str(e))

    def _done(self, task: dict) -> None:
        self.running = False
        self.status.configure(text="完成 ✓")
        self.refresh()
        self.app._refresh_badge()

    def _error(self, task: dict | None) -> None:
        self.running = False
        self.status.configure(text="失败")
        messagebox.showerror("执行失败", (task or {}).get("error", "任务执行失败"))
        self.refresh()

    def _delete_artifact(self) -> None:
        selection = selection_for_step(self.step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        artifact = get_artifact_for_step(self.shared.current_snapshot, self.step, selection)
        if not artifact:
            return
        if not messagebox.askyesno("确认删除", f"删除产物 '{artifact.get('key', '')}' 将级联清理下游产物，确定继续？"):
            return
        try:
            self.shared.container.project_service.remove_artifact(self.shared.current_project_id, artifact.get("key", ""))
            self.refresh()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))


# ---------------------------------------------------------------------------
# Review page
# ---------------------------------------------------------------------------


class ReviewView(ctk.CTkFrame):
    def __init__(self, master: Any, app: ModernApp) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.metrics = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self.metrics.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.tabs = ctk.CTkTabview(self, corner_radius=24, fg_color=C["card"], segmented_button_selected_color=C["primary"])
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.summary = self.tabs.add("总览")
        self.matrix = self.tabs.add("进度矩阵")
        self.tasks = self.tabs.add("任务记录")
        for tab in (self.summary, self.matrix, self.tasks):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

    def refresh(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            self.shared.current_snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
            return
        self._metrics()
        self._summary()
        self._matrix()
        self._tasks()

    def _metrics(self) -> None:
        for child in self.metrics.winfo_children():
            child.destroy()
        artifacts = (self.shared.current_snapshot or {}).get("artifacts", {}) or {}
        tasks = self.shared.current_tasks
        stats = [("总步骤", "12", C["primary"]), ("已产出", str(len(artifacts)), C["green"]), ("失败任务", str(sum(1 for t in tasks if t.get("status") == "failed")), C["red"]), ("进行中", str(sum(1 for t in tasks if t.get("status") in ("running", "pending"))), C["amber"]), ("任务总数", str(len(tasks)), C["blue"])]
        for i, (label, value, color) in enumerate(stats):
            Metric(self.metrics, label, value, color).grid(row=0, column=i, sticky="ew", padx=6)

    def _summary(self) -> None:
        for child in self.summary.winfo_children():
            child.destroy()
        pi = ((self.shared.current_snapshot or {}).get("project", {}) or {}).get("input", {}) or {}
        box = ctk.CTkTextbox(self.summary, corner_radius=18, fg_color=C["soft"], text_color=C["text"], wrap="word")
        box.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        box.insert("1.0", "\n".join([f"标题：{pi.get('title', '未知')}", f"类型：{pi.get('genre', '未知')}", f"目标字数：{pi.get('target_words', 0)}", f"卷/章：{pi.get('target_volume_count', 1)} 卷 × {pi.get('target_chapters_per_volume', 12)} 章", "", "前提：", str(pi.get("premise", "（未设置）"))]))
        box.configure(state="disabled")

    def _matrix(self) -> None:
        for child in self.matrix.winfo_children():
            child.destroy()
        frame = Scroll(self.matrix)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        for group in REVIEW_GROUPS:
            ctk.CTkLabel(frame, text=group["label"], font=(FONT, 16, "bold"), text_color=C["text"]).pack(anchor="w", pady=(12, 6))
            for step_key in group["steps"]:
                selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
                status = get_step_status(step_key, self.shared.current_snapshot, self.shared.current_tasks, selection)
                artifact = get_artifact_for_step(self.shared.current_snapshot, step_key, selection)
                row = ctk.CTkFrame(frame, fg_color=C["soft"], corner_radius=15)
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text=get_step_label(step_key), width=170, anchor="w", font=(FONT, 13, "bold"), text_color=C["text"]).pack(side="left", padx=14, pady=10)
                ctk.CTkLabel(row, text=status.get("text", ""), width=90, font=(FONT, 12), text_color=C["primary"]).pack(side="left")
                ctk.CTkLabel(row, text=(artifact or {}).get("key", "—"), anchor="w", font=(FONT, 12), text_color=C["muted"]).pack(side="left", fill="x", expand=True, padx=8)

    def _tasks(self) -> None:
        for child in self.tasks.winfo_children():
            child.destroy()
        frame = Scroll(self.tasks)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        tasks = sorted(self.shared.current_tasks, key=lambda t: str(t.get("created_at", "")), reverse=True)
        if not tasks:
            ctk.CTkLabel(frame, text="暂无任务记录", font=(FONT, 14), text_color=C["muted"]).pack(pady=32)
            return
        for t in tasks[:80]:
            status = t.get("status", "")
            color = {"completed": C["green"], "failed": C["red"], "running": C["blue"], "pending": C["amber"]}.get(status, C["muted"])
            row = ctk.CTkFrame(frame, fg_color=C["soft"], corner_radius=15)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=status, width=95, font=(FONT, 12, "bold"), text_color=color).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=t.get("task_name", ""), width=150, anchor="w", font=(FONT, 12), text_color=C["text"]).pack(side="left")
            ctk.CTkLabel(row, text=str(t.get("created_at", ""))[:19], font=(FONT, 12), text_color=C["muted"]).pack(side="right", padx=12)


def main() -> None:
    app = ModernApp()
    app.mainloop()
