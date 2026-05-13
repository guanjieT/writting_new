"""Modern CustomTkinter desktop interface for Novel Agent.

This module intentionally replaces the old ttk-heavy shell with a native-looking
CustomTkinter experience while keeping the existing service/orchestrator layer.
Run with: python -m novel_agent.gui
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover - user-facing startup guard
    raise SystemExit(
        "CustomTkinter is required for the new GUI. Install it with:\n"
        "    pip install customtkinter\n"
        "or install the GUI requirements file if present."
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
    get_dependency_states,
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
    STATUS_COLORS,
    get_step_def,
    get_step_label,
)
from .task_monitor import TaskMonitor


COLORS = {
    "bg": "#0b1020",
    "surface": "#111827",
    "surface_2": "#162033",
    "surface_3": "#1f2937",
    "panel": "#f8fafc",
    "card": "#ffffff",
    "card_2": "#f1f5f9",
    "text": "#0f172a",
    "muted": "#64748b",
    "muted_dark": "#94a3b8",
    "white": "#ffffff",
    "accent": "#7c3aed",
    "accent_2": "#2563eb",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "border": "#e2e8f0",
}

FONT = "Microsoft YaHei UI"


def _as_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _project_input_dict(project: Any) -> dict:
    if isinstance(project, dict):
        return project.get("input", {}) or {}
    pi = getattr(project, "input", None)
    if pi is None:
        return {}
    if hasattr(pi, "model_dump"):
        return pi.model_dump(mode="json")
    return _as_dict(pi)


def _project_id(project: Any) -> str:
    if isinstance(project, dict):
        return str(project.get("project_id", ""))
    return str(getattr(project, "project_id", ""))


def _project_status(project: Any) -> str:
    status = project.get("status", "") if isinstance(project, dict) else getattr(project, "status", "")
    return str(status.value if hasattr(status, "value") else status)


def _list_to_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    if value is None:
        return ""
    return str(value)


class ScrollFrame(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", scrollbar_button_color="#cbd5e1", scrollbar_button_hover_color="#94a3b8", **kwargs)


class MetricCard(ctk.CTkFrame):
    def __init__(self, master: Any, label: str, value: str, color: str = COLORS["accent"]) -> None:
        super().__init__(master, fg_color=COLORS["card"], corner_radius=18, border_width=1, border_color=COLORS["border"])
        ctk.CTkLabel(self, text=value, text_color=color, font=(FONT, 24, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(self, text=label, text_color=COLORS["muted"], font=(FONT, 12)).pack(anchor="w", padx=18, pady=(0, 14))


class AppCTk(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("Novel Agent — 小说创作工作台")
        self.geometry("1480x940")
        self.minsize(1180, 720)
        self.configure(fg_color=COLORS["panel"])

        config = load_config()
        self.container = build_container(config)
        self.shared = AppShared(
            container=self.container,
            task_monitor=TaskMonitor(self, self.container.task_service),
        )

        self._views: dict[str, Any] = {}
        self._current_view = "project"
        self._build_layout()
        self.switch_view("project")

    # ------------------------------------------------------------------
    # Shell
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=292, corner_radius=0, fg_color=COLORS["bg"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["panel"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_topbar()

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._views = {
            "project": ProjectPage(self.content, self),
            "workflow": WorkflowPage(self.content, self),
            "review": ReviewPage(self.content, self),
        }

    def _build_sidebar(self) -> None:
        ctk.CTkLabel(self.sidebar, text="✦ Novel Agent", text_color=COLORS["white"], font=(FONT, 24, "bold")).pack(anchor="w", padx=24, pady=(26, 2))
        ctk.CTkLabel(self.sidebar, text="AI fiction studio", text_color=COLORS["muted_dark"], font=(FONT, 13)).pack(anchor="w", padx=26, pady=(0, 22))

        self.project_card = ctk.CTkFrame(self.sidebar, fg_color=COLORS["surface_2"], corner_radius=20)
        self.project_card.pack(fill="x", padx=18, pady=(0, 20))
        ctk.CTkLabel(self.project_card, text="当前项目", text_color=COLORS["muted_dark"], font=(FONT, 12)).pack(anchor="w", padx=18, pady=(16, 0))
        self.project_title = ctk.CTkLabel(self.project_card, text="未选择", text_color=COLORS["white"], font=(FONT, 17, "bold"), wraplength=220, justify="left")
        self.project_title.pack(anchor="w", padx=18, pady=(4, 2))
        self.project_meta = ctk.CTkLabel(self.project_card, text="先创建或选择作品", text_color=COLORS["muted_dark"], font=(FONT, 12), wraplength=220, justify="left")
        self.project_meta.pack(anchor="w", padx=18, pady=(0, 16))

        ctk.CTkLabel(self.sidebar, text="导航", text_color=COLORS["muted_dark"], font=(FONT, 12, "bold")).pack(anchor="w", padx=24, pady=(0, 8))
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in [("project", "项目中心"), ("workflow", "创作工作台"), ("review", "审查面板")]:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                height=44,
                corner_radius=14,
                anchor="w",
                fg_color="transparent",
                hover_color=COLORS["surface_2"],
                text_color="#dbeafe",
                font=(FONT, 14, "bold"),
                command=lambda k=key: self.switch_view(k),
            )
            btn.pack(fill="x", padx=18, pady=4)
            self.nav_buttons[key] = btn

        self.scope_card = ctk.CTkFrame(self.sidebar, fg_color=COLORS["surface_2"], corner_radius=18)
        self.scope_card.pack(fill="x", padx=18, pady=(22, 0))
        ctk.CTkLabel(self.scope_card, text="创作范围", text_color=COLORS["white"], font=(FONT, 14, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.volume_menu = ctk.CTkOptionMenu(self.scope_card, values=["第 1 卷"], command=lambda _v: self._on_scope_change(), fg_color=COLORS["surface_3"], button_color=COLORS["accent"], corner_radius=12)
        self.volume_menu.pack(fill="x", padx=14, pady=5)
        self.chapter_menu = ctk.CTkOptionMenu(self.scope_card, values=["第 1 章"], command=lambda _v: self._on_scope_change(), fg_color=COLORS["surface_3"], button_color=COLORS["accent"], corner_radius=12)
        self.chapter_menu.pack(fill="x", padx=14, pady=(5, 16))

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=24, pady=22)
        ctk.CTkLabel(bottom, text="任务状态", text_color=COLORS["muted_dark"], font=(FONT, 12, "bold")).pack(anchor="w")
        self.task_status = ctk.CTkLabel(bottom, text="● 无运行任务", text_color=COLORS["muted_dark"], font=(FONT, 12))
        self.task_status.pack(anchor="w", pady=(4, 0))

    def _build_topbar(self) -> None:
        top = ctk.CTkFrame(self.main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 18))
        top.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(top, text="项目中心", text_color=COLORS["text"], font=(FONT, 28, "bold"))
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_hint = ctk.CTkLabel(top, text="管理作品设定与创作入口", text_color=COLORS["muted"], font=(FONT, 13))
        self.page_hint.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.refresh_btn = ctk.CTkButton(top, text="刷新", width=96, height=36, corner_radius=12, fg_color=COLORS["surface_3"], hover_color=COLORS["surface_2"], command=self.refresh_current)
        self.refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e")

    def switch_view(self, name: str) -> None:
        if name in ("workflow", "review") and not self.shared.current_project_id:
            messagebox.showwarning("未选择项目", "请先在项目中心选择或创建一个项目。")
            name = "project"

        for key, view in self._views.items():
            if key == name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        self._current_view = name
        meta = {
            "project": ("项目中心", "创建、选择并维护作品蓝图"),
            "workflow": ("创作工作台", "按依赖顺序推进设定、纲要、章节和审查"),
            "review": ("审查面板", "集中查看进度、任务历史和质量阻塞项"),
        }
        title, hint = meta[name]
        self.page_title.configure(text=title)
        self.page_hint.configure(text=hint)

        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=COLORS["accent"], text_color=COLORS["white"], hover_color="#6d28d9")
            else:
                btn.configure(fg_color="transparent", text_color="#dbeafe", hover_color=COLORS["surface_2"])

        self.refresh_current()

    def refresh_current(self) -> None:
        self._refresh_scope_options()
        self._refresh_project_badge()
        view = self._views.get(self._current_view)
        if view and hasattr(view, "refresh"):
            view.refresh()

    def _refresh_project_badge(self) -> None:
        project = self.shared.project()
        if project:
            pi = project.get("input", {}) or {}
            self.project_title.configure(text=pi.get("title", "未命名"))
            genre = pi.get("genre", "")
            status = project.get("status", "")
            self.project_meta.configure(text=f"{genre}\n状态：{status}" if genre else f"状态：{status}")
        else:
            self.project_title.configure(text="未选择")
            self.project_meta.configure(text="先创建或选择作品")
        active = self.shared.task_monitor.active_count
        if active:
            self.task_status.configure(text=f"● 运行中：{active} 个任务", text_color="#bfdbfe")
        else:
            self.task_status.configure(text="● 无运行任务", text_color=COLORS["muted_dark"])

    def _refresh_scope_options(self) -> None:
        snapshot = self.shared.current_snapshot
        volumes = get_volume_entry_options(snapshot) or [{"value": "1", "label": "第 1 卷"}]
        self._volume_options = volumes
        self.volume_menu.configure(values=[v["label"] for v in volumes])
        cur_v = str(self.shared.scope.volume_index or 1)
        vol = next((v for v in volumes if v["value"] == cur_v), volumes[0])
        self.volume_menu.set(vol["label"])

        chapters = get_chapter_entry_options(snapshot, int(vol["value"])) or [{"value": "1", "label": "第 1 章"}]
        self._chapter_options = chapters
        self.chapter_menu.configure(values=[c["label"] for c in chapters])
        cur_c = str(self.shared.scope.chapter_index or 1)
        ch = next((c for c in chapters if c["value"] == cur_c), chapters[0])
        self.chapter_menu.set(ch["label"])

    def _on_scope_change(self) -> None:
        v_label = self.volume_menu.get()
        c_label = self.chapter_menu.get()
        for opt in getattr(self, "_volume_options", []):
            if opt["label"] == v_label:
                self.shared.scope.volume_index = int(opt["value"])
                break
        for opt in getattr(self, "_chapter_options", []):
            if opt["label"] == c_label:
                self.shared.scope.chapter_index = int(opt["value"])
                break
        if self._current_view in ("workflow", "review"):
            self.refresh_current()


class ProjectPage(ctk.CTkFrame):
    def __init__(self, master: Any, app: AppCTk) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self._widgets: dict[str, Any] = {}
        self._project_ids: list[str] = []
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        left = ctk.CTkFrame(self, width=360, fg_color=COLORS["card"], corner_radius=24, border_width=1, border_color=COLORS["border"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="作品库", text_color=COLORS["text"], font=(FONT, 22, "bold")).pack(anchor="w", padx=22, pady=(22, 0))
        ctk.CTkLabel(left, text="选择一个作品继续创作", text_color=COLORS["muted"], font=(FONT, 13)).pack(anchor="w", padx=22, pady=(2, 16))

        stats = ctk.CTkFrame(left, fg_color="transparent")
        stats.pack(fill="x", padx=18, pady=(0, 12))
        stats.grid_columnconfigure((0, 1), weight=1)
        self.project_count_card = MetricCard(stats, "项目", "0", COLORS["accent"])
        self.project_count_card.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.selected_card = MetricCard(stats, "当前", "未选", COLORS["accent_2"])
        self.selected_card.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.project_list = ScrollFrame(left)
        self.project_list.pack(fill="both", expand=True, padx=18, pady=(4, 18))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(right, fg_color="#ede9fe", corner_radius=24)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ctk.CTkLabel(hero, text="作品蓝图", text_color="#2e1065", font=(FONT, 28, "bold")).pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(hero, text="把题材、前提、规模和风格约束整理为统一源头，后续所有生成步骤都基于这里。", text_color="#6b21a8", font=(FONT, 14), wraplength=820, justify="left").pack(anchor="w", padx=24, pady=(0, 22))

        self.form = ScrollFrame(right)
        self.form.grid(row=1, column=0, sticky="nsew")
        self._build_form()

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.create_btn = ctk.CTkButton(actions, text="＋ 创建项目", height=42, corner_radius=14, fg_color=COLORS["accent"], hover_color="#6d28d9", command=self._create_project)
        self.create_btn.pack(side="left")
        self.update_btn = ctk.CTkButton(actions, text="保存修改", height=42, corner_radius=14, fg_color=COLORS["surface_3"], hover_color=COLORS["surface_2"], state="disabled", command=self._update_project)
        self.update_btn.pack(side="left", padx=10)
        self.delete_btn = ctk.CTkButton(actions, text="删除", height=42, corner_radius=14, fg_color=COLORS["danger"], hover_color="#b91c1c", state="disabled", command=self._delete_project)
        self.delete_btn.pack(side="left")
        self.open_btn = ctk.CTkButton(actions, text="进入创作工作台 →", height=42, corner_radius=14, fg_color=COLORS["accent_2"], hover_color="#1d4ed8", state="disabled", command=lambda: self.app.switch_view("workflow"))
        self.open_btn.pack(side="right")

    def _build_form(self) -> None:
        sections = [
            ("作品定位", [("title", "作品标题", "text", 0), ("genre", "作品类型", "text", 0), ("premise", "前提/核心构思", "textarea", 5), ("target_audience", "目标受众", "text", 0)]),
            ("规模与节奏", [("target_words", "目标总字数", "number", 0), ("target_volume_count", "目标卷数", "number", 0), ("target_chapters_per_volume", "每卷章节数", "number", 0)]),
            ("风格与约束", [("tone", "基调标签（一行一个）", "list", 4), ("style", "风格标签（一行一个）", "list", 4), ("outline_focus", "总纲关注点（一行一个）", "list", 4), ("core_requirements", "核心要求（一行一个）", "list", 4), ("forbidden_elements", "禁忌元素（一行一个）", "list", 4)]),
        ]
        for title, fields in sections:
            card = ctk.CTkFrame(self.form, fg_color=COLORS["card"], corner_radius=20, border_width=1, border_color=COLORS["border"])
            card.pack(fill="x", padx=4, pady=(0, 14))
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=title, text_color=COLORS["text"], font=(FONT, 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 10))
            for i, (key, label, typ, rows) in enumerate(fields, start=1):
                ctk.CTkLabel(card, text=label, text_color=COLORS["muted"], font=(FONT, 13)).grid(row=i, column=0, sticky="nw", padx=(20, 18), pady=8)
                if typ in ("textarea", "list"):
                    w = ctk.CTkTextbox(card, height=max(rows, 3) * 28, corner_radius=12, border_width=1, border_color=COLORS["border"], fg_color=COLORS["card_2"], text_color=COLORS["text"])
                    w.grid(row=i, column=1, sticky="ew", padx=(0, 20), pady=8)
                    self._widgets[key] = (typ, w)
                else:
                    w = ctk.CTkEntry(card, height=40, corner_radius=12, border_width=1, border_color=COLORS["border"], fg_color=COLORS["card_2"], text_color=COLORS["text"])
                    w.grid(row=i, column=1, sticky="ew", padx=(0, 20), pady=8)
                    self._widgets[key] = (typ, w)

    def _read_form(self) -> dict:
        payload: dict[str, Any] = {}
        for key, (typ, widget) in self._widgets.items():
            value = widget.get("1.0", "end-1c") if typ in ("textarea", "list") else widget.get()
            if typ == "list":
                payload[key] = [line.strip() for line in value.splitlines() if line.strip()]
            elif typ == "number":
                payload[key] = int(value) if str(value).strip().isdigit() else 0
            else:
                payload[key] = value
        return payload

    def _set_form(self, data: dict) -> None:
        for key, (typ, widget) in self._widgets.items():
            value = data.get(key, "")
            text = _list_to_text(value)
            if typ in ("textarea", "list"):
                widget.delete("1.0", "end")
                widget.insert("1.0", text)
            else:
                widget.delete(0, "end")
                widget.insert(0, text)

    def _clear_form(self) -> None:
        self._set_form({})

    def refresh(self) -> None:
        try:
            projects = self.shared.container.orchestrator.list_projects()
        except Exception:
            projects = []
        self._project_ids = []
        for child in self.project_list.winfo_children():
            child.destroy()
        for project in projects:
            pid = _project_id(project)
            pi = _project_input_dict(project)
            self._project_ids.append(pid)
            selected = pid == self.shared.current_project_id
            btn = ctk.CTkButton(
                self.project_list,
                text=f"{pi.get('title', '未命名')}\n{pi.get('genre', '')} · {_project_status(project)}",
                height=62,
                corner_radius=16,
                anchor="w",
                justify="left",
                fg_color=COLORS["accent"] if selected else COLORS["card_2"],
                hover_color="#6d28d9" if selected else "#e2e8f0",
                text_color=COLORS["white"] if selected else COLORS["text"],
                font=(FONT, 13, "bold"),
                command=lambda p=pid: self._select_project(p),
            )
            btn.pack(fill="x", pady=6)
        self.project_count_card.destroy()
        self.selected_card.destroy()
        # Rebuild metric cards in parent frame
        stats = self.project_list.master.winfo_children()[2]
        for c in stats.winfo_children():
            c.destroy()
        MetricCard(stats, "项目", str(len(projects)), COLORS["accent"]).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        MetricCard(stats, "当前", "已选" if self.shared.current_project_id else "未选", COLORS["accent_2"]).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        if self.shared.current_project_id:
            self._load_snapshot()
        else:
            self._clear_form()
            self.update_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
            self.open_btn.configure(state="disabled")

    def _select_project(self, pid: str) -> None:
        self.shared.current_project_id = pid
        self._load_snapshot()
        self.app.refresh_current()

    def _load_snapshot(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_snapshot = snapshot
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
            project = snapshot.get("project", {})
            self._set_form(project.get("input", {}) or {})
            self.update_btn.configure(state="normal")
            self.delete_btn.configure(state="normal")
            self.open_btn.configure(state="normal")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _create_project(self) -> None:
        payload = self._read_form()
        if not payload.get("title") or not payload.get("genre"):
            messagebox.showwarning("缺少信息", "作品标题和类型为必填项。")
            return
        try:
            project_input = ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])})
            project = self.shared.container.orchestrator.create_project(project_input)
            self.shared.current_project_id = project.project_id
            self.app.refresh_current()
            messagebox.showinfo("成功", f"项目 '{project.input.title}' 创建成功。")
        except Exception as e:
            messagebox.showerror("创建失败", str(e))

    def _update_project(self) -> None:
        if not self.shared.current_project_id:
            return
        if not messagebox.askyesno("确认更新", "更新项目会清除已有产物和历史记录，确定继续？"):
            return
        try:
            payload = self._read_form()
            project_input = ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])})
            self.shared.container.orchestrator.update_project(self.shared.current_project_id, project_input)
            self.app.refresh_current()
            messagebox.showinfo("成功", "项目已更新。")
        except Exception as e:
            messagebox.showerror("更新失败", str(e))

    def _delete_project(self) -> None:
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
            self.app.refresh_current()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))


class WorkflowPage(ctk.CTkFrame):
    def __init__(self, master: Any, app: AppCTk) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self._current_step = ""
        self._field_widgets: dict[str, tuple[str, Any, Any]] = {}
        self._running = False
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        self.steps_panel = ctk.CTkFrame(self, width=282, fg_color=COLORS["card"], corner_radius=24, border_width=1, border_color=COLORS["border"])
        self.steps_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.steps_panel.grid_propagate(False)
        ctk.CTkLabel(self.steps_panel, text="生成步骤", text_color=COLORS["text"], font=(FONT, 21, "bold")).pack(anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(self.steps_panel, text="按依赖顺序推进", text_color=COLORS["muted"], font=(FONT, 12)).pack(anchor="w", padx=20, pady=(0, 12))
        self.step_scroll = ScrollFrame(self.steps_panel)
        self.step_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 16))
        self.step_buttons: dict[str, ctk.CTkButton] = {}

        self.editor = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=24, border_width=1, border_color=COLORS["border"])
        self.editor.grid(row=0, column=1, sticky="nsew", padx=(0, 18))
        self.editor.grid_rowconfigure(2, weight=1)
        self.editor.grid_columnconfigure(0, weight=1)

        self.step_title = ctk.CTkLabel(self.editor, text="选择步骤", text_color=COLORS["text"], font=(FONT, 24, "bold"))
        self.step_title.grid(row=0, column=0, sticky="w", padx=22, pady=(20, 0))
        self.step_desc = ctk.CTkLabel(self.editor, text="从左侧选择一个生成步骤。", text_color=COLORS["muted"], font=(FONT, 13), wraplength=560, justify="left")
        self.step_desc.grid(row=1, column=0, sticky="w", padx=22, pady=(2, 10))

        self.form = ScrollFrame(self.editor)
        self.form.grid(row=2, column=0, sticky="nsew", padx=16, pady=0)

        actions = ctk.CTkFrame(self.editor, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=16)
        self.generate_btn = ctk.CTkButton(actions, text="生成", height=42, corner_radius=14, fg_color=COLORS["accent"], hover_color="#6d28d9", state="disabled", command=self._run_step)
        self.generate_btn.pack(side="left")
        self.delete_btn = ctk.CTkButton(actions, text="删除产物", height=42, corner_radius=14, fg_color=COLORS["danger"], hover_color="#b91c1c", state="disabled", command=self._delete_artifact)
        self.delete_btn.pack(side="left", padx=10)
        self.status = ctk.CTkLabel(actions, text="", text_color=COLORS["muted"], font=(FONT, 12))
        self.status.pack(side="right")

        self.viewer = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=24, border_width=1, border_color=COLORS["border"])
        self.viewer.grid(row=0, column=2, sticky="nsew")
        self.viewer.grid_rowconfigure(1, weight=1)
        self.viewer.grid_columnconfigure(0, weight=1)

    def _build_steps(self) -> None:
        for child in self.step_scroll.winfo_children():
            child.destroy()
        self.step_buttons = {}
        for group in PAGE_STEP_GROUPS["workflow"]:
            ctk.CTkLabel(self.step_scroll, text=group["label"], text_color=COLORS["muted"], font=(FONT, 12, "bold")).pack(anchor="w", padx=8, pady=(12, 4))
            for step_key in group["steps"]:
                label = get_step_def(step_key).label
                status = get_step_status(step_key, self.shared.current_snapshot, self.shared.current_tasks, selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index}))
                text = f"{label}    {status.get('text', '')}"
                selected = step_key == self._current_step
                btn = ctk.CTkButton(
                    self.step_scroll,
                    text=text,
                    height=38,
                    corner_radius=12,
                    anchor="w",
                    fg_color=COLORS["accent"] if selected else COLORS["card_2"],
                    hover_color="#6d28d9" if selected else "#e2e8f0",
                    text_color=COLORS["white"] if selected else COLORS["text"],
                    font=(FONT, 12, "bold"),
                    command=lambda sk=step_key: self._select_step(sk),
                )
                btn.pack(fill="x", padx=4, pady=3)
                self.step_buttons[step_key] = btn

    def _select_step(self, step_key: str) -> None:
        self._current_step = step_key
        self.shared.current_step = step_key
        self._render_step()
        self._build_steps()

    def _render_step(self) -> None:
        for child in self.form.winfo_children():
            child.destroy()
        self._field_widgets = {}
        if not self._current_step:
            return
        step_def = get_step_def(self._current_step)
        self.step_title.configure(text=step_def.label)
        self.step_desc.configure(text=step_def.description)
        selection = selection_for_step(self._current_step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        msg = get_step_readiness_message(self._current_step, self.shared.current_snapshot, selection)
        if msg:
            warn = ctk.CTkFrame(self.form, fg_color="#fef3c7", corner_radius=14)
            warn.pack(fill="x", padx=4, pady=(0, 12))
            ctk.CTkLabel(warn, text=msg, text_color="#92400e", font=(FONT, 13), wraplength=560, justify="left").pack(anchor="w", padx=14, pady=12)

        for field in step_def.fields:
            card = ctk.CTkFrame(self.form, fg_color=COLORS["card_2"], corner_radius=16)
            card.pack(fill="x", padx=4, pady=6)
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=field.label, text_color=COLORS["text"], font=(FONT, 13, "bold")).grid(row=0, column=0, sticky="nw", padx=14, pady=12)
            default = get_field_display_value(field, self.shared.current_snapshot, selection)
            setattr(field, "step_key", self._current_step)
            widget = self._build_field_widget(card, field, default, selection)
            widget.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=10)

        ready = is_unlocked(self._current_step, self.shared.current_snapshot, selection)
        self.generate_btn.configure(state="normal" if ready and not self._running else "disabled")
        artifact = get_artifact_for_step(self.shared.current_snapshot, self._current_step, selection)
        self.delete_btn.configure(state="normal" if artifact else "disabled")
        self._render_viewer(artifact)

    def _build_field_widget(self, parent: Any, field: Any, default: Any, selection: dict) -> Any:
        key = field.key
        typ = field.field_type
        if typ in (FIELD_TEXTAREA, FIELD_LIST):
            w = ctk.CTkTextbox(parent, height=max(field.rows or 4, 3) * 28, corner_radius=12, border_width=1, border_color=COLORS["border"], fg_color=COLORS["card"], text_color=COLORS["text"])
            w.insert("1.0", _list_to_text(default))
            self._field_widgets[key] = ("text", w, field)
            return w
        if typ == FIELD_CHECKBOX:
            var = tk.BooleanVar(value=bool(default))
            w = ctk.CTkCheckBox(parent, text="", variable=var, fg_color=COLORS["accent"])
            self._field_widgets[key] = ("checkbox", var, field)
            return w
        if typ == FIELD_SELECT:
            options = get_field_select_options(field, self.shared.current_snapshot, selection)
            if not options and field.option_source == "current_artifacts":
                options = get_current_artifact_options(self.shared.current_snapshot, selection)
            values = [o["label"] for o in options] or [field.empty_label or "无可选项"]
            value_by_label = {o["label"]: o["value"] for o in options}
            label_by_value = {str(o["value"]): o["label"] for o in options}
            w = ctk.CTkOptionMenu(parent, values=values, fg_color=COLORS["card"], button_color=COLORS["accent"], text_color=COLORS["text"], corner_radius=12)
            w.set(label_by_value.get(str(default), values[0]))
            if field.disabled:
                w.configure(state="disabled")
            self._field_widgets[key] = ("select", (w, value_by_label), field)
            return w
        w = ctk.CTkEntry(parent, height=38, corner_radius=12, border_width=1, border_color=COLORS["border"], fg_color=COLORS["card"], text_color=COLORS["text"])
        w.insert(0, _list_to_text(default))
        self._field_widgets[key] = ("entry", w, field)
        return w

    def _read_payload(self) -> dict:
        payload: dict[str, Any] = {}
        for key, (kind, target, field) in self._field_widgets.items():
            if kind == "text":
                raw = target.get("1.0", "end-1c")
                payload[key] = [line.strip() for line in raw.splitlines() if line.strip()] if getattr(field, "is_list", False) or field.field_type == FIELD_LIST else raw
            elif kind == "checkbox":
                payload[key] = bool(target.get())
            elif kind == "select":
                widget, value_by_label = target
                payload[key] = value_by_label.get(widget.get(), widget.get())
            else:
                raw = target.get()
                if field.field_type == FIELD_NUMBER:
                    try:
                        payload[key] = int(float(raw))
                    except (ValueError, TypeError):
                        payload[key] = 0
                else:
                    payload[key] = raw
        return payload

    def _render_viewer(self, artifact: dict | None) -> None:
        for child in self.viewer.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.viewer, text="产物预览", text_color=COLORS["text"], font=(FONT, 21, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        box = ctk.CTkTextbox(self.viewer, corner_radius=16, border_width=1, border_color=COLORS["border"], fg_color=COLORS["card_2"], text_color=COLORS["text"], wrap="word")
        box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        if not artifact:
            box.insert("1.0", "暂无产物。\n\n生成当前步骤后，这里会展示正文、摘要和元数据。")
        else:
            meta = artifact.get("metadata", {}) or {}
            content = artifact.get("content") or (meta.get("generated_payload", {}) or {}).get("content") or ""
            lines = [f"标题：{artifact.get('title') or get_step_label(self._current_step)}", f"键：{artifact.get('key', '')}", "", str(content or "（无内容）")]
            if artifact.get("summary"):
                lines.extend(["", "—— 摘要 ——", json.dumps(artifact.get("summary"), ensure_ascii=False, indent=2, default=str)])
            box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    def _run_step(self) -> None:
        if not self._current_step or self._running:
            return
        selection = selection_for_step(self._current_step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        if not is_unlocked(self._current_step, self.shared.current_snapshot, selection):
            messagebox.showwarning("依赖未就绪", get_step_readiness_message(self._current_step, self.shared.current_snapshot, selection))
            return
        payload = self._read_payload()
        base = build_base_artifact_payload(self._current_step, self.shared.current_snapshot, selection)
        if base:
            payload["base_artifact"] = base
        self._running = True
        self.generate_btn.configure(state="disabled")
        self.status.configure(text="生成中...")
        try:
            scope = task_scope_from_payload(self._current_step, payload)

            def _job() -> Any:
                result = self.shared.container.orchestrator.dispatch(self.shared.current_project_id, self._current_step, payload)
                return result.model_dump(mode="json") if hasattr(result, "model_dump") else result

            task = self.shared.container.task_service.submit(
                project_id=self.shared.current_project_id,
                task_name=self._current_step,
                job=_job,
                scope=scope,
                input_payload=payload,
            )
            self.shared.task_monitor.start(task.task_id, on_complete=self._task_done, on_error=self._task_error)
        except Exception as e:
            self._running = False
            self.status.configure(text="")
            self.generate_btn.configure(state="normal")
            messagebox.showerror("提交失败", str(e))

    def _task_done(self, task: dict) -> None:
        self._running = False
        self.status.configure(text="完成 ✓")
        self._reload_project()
        self._render_step()
        self._build_steps()
        self.app._refresh_project_badge()

    def _task_error(self, task: dict | None) -> None:
        self._running = False
        self.status.configure(text="失败")
        self._reload_project()
        messagebox.showerror("执行失败", (task or {}).get("error", "任务执行失败"))
        self._render_step()
        self._build_steps()

    def _reload_project(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            self.shared.current_snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
        except Exception:
            pass

    def _delete_artifact(self) -> None:
        selection = selection_for_step(self._current_step, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        artifact = get_artifact_for_step(self.shared.current_snapshot, self._current_step, selection)
        if not artifact:
            return
        if not messagebox.askyesno("确认删除", f"删除产物 '{artifact.get('key', '')}' 将级联清理下游产物，确定继续？"):
            return
        try:
            self.shared.container.project_service.remove_artifact(self.shared.current_project_id, artifact.get("key", ""))
            self._reload_project()
            self._render_step()
            self._build_steps()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def refresh(self) -> None:
        self._reload_project()
        self._build_steps()
        if not self._current_step:
            first = PAGE_STEP_GROUPS["workflow"][0]["steps"][0]
            self._select_step(first)
        else:
            self._render_step()


class ReviewPage(ctk.CTkFrame):
    def __init__(self, master: Any, app: AppCTk) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.shared = app.shared
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self) -> None:
        self.metrics = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self.metrics.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.tabs = ctk.CTkTabview(self, fg_color=COLORS["card"], segmented_button_fg_color=COLORS["card_2"], segmented_button_selected_color=COLORS["accent"], corner_radius=24)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.summary_tab = self.tabs.add("总览")
        self.matrix_tab = self.tabs.add("进度矩阵")
        self.tasks_tab = self.tabs.add("任务记录")
        for tab in (self.summary_tab, self.matrix_tab, self.tasks_tab):
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
        self._render_metrics()
        self._render_summary()
        self._render_matrix()
        self._render_tasks()

    def _render_metrics(self) -> None:
        for child in self.metrics.winfo_children():
            child.destroy()
        snapshot = self.shared.current_snapshot or {}
        artifacts = snapshot.get("artifacts", {}) or {}
        tasks = self.shared.current_tasks
        stats = [
            ("总步骤", "12", COLORS["accent"]),
            ("已产出", str(len(artifacts)), COLORS["success"]),
            ("失败任务", str(sum(1 for t in tasks if t.get("status") == "failed")), COLORS["danger"]),
            ("进行中", str(sum(1 for t in tasks if t.get("status") in ("running", "pending"))), COLORS["warning"]),
            ("任务总数", str(len(tasks)), COLORS["accent_2"]),
        ]
        for i, (label, value, color) in enumerate(stats):
            MetricCard(self.metrics, label, value, color).grid(row=0, column=i, sticky="ew", padx=6)

    def _render_summary(self) -> None:
        for child in self.summary_tab.winfo_children():
            child.destroy()
        snapshot = self.shared.current_snapshot or {}
        project = snapshot.get("project", {}) or {}
        pi = project.get("input", {}) or {}
        text = ctk.CTkTextbox(self.summary_tab, corner_radius=18, fg_color=COLORS["card_2"], text_color=COLORS["text"], wrap="word")
        text.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        lines = [
            f"标题：{pi.get('title', '未知')}",
            f"类型：{pi.get('genre', '未知')}",
            f"目标字数：{pi.get('target_words', 0)}",
            f"卷/章：{pi.get('target_volume_count', 1)} 卷 × {pi.get('target_chapters_per_volume', 12)} 章",
            "",
            "前提：",
            str(pi.get("premise", "（未设置）")),
        ]
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def _render_matrix(self) -> None:
        for child in self.matrix_tab.winfo_children():
            child.destroy()
        frame = ScrollFrame(self.matrix_tab)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        for group in REVIEW_GROUPS:
            ctk.CTkLabel(frame, text=group["label"], text_color=COLORS["text"], font=(FONT, 16, "bold")).pack(anchor="w", pady=(12, 6))
            for step_key in group["steps"]:
                selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
                status = get_step_status(step_key, self.shared.current_snapshot, self.shared.current_tasks, selection)
                artifact = get_artifact_for_step(self.shared.current_snapshot, step_key, selection)
                row = ctk.CTkFrame(frame, fg_color=COLORS["card_2"], corner_radius=14)
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text=get_step_label(step_key), text_color=COLORS["text"], font=(FONT, 13, "bold"), width=160, anchor="w").pack(side="left", padx=14, pady=10)
                ctk.CTkLabel(row, text=status.get("text", ""), text_color=COLORS["accent"], font=(FONT, 12), width=80).pack(side="left")
                ctk.CTkLabel(row, text=(artifact or {}).get("key", "—"), text_color=COLORS["muted"], font=(FONT, 12), anchor="w").pack(side="left", fill="x", expand=True, padx=8)

    def _render_tasks(self) -> None:
        for child in self.tasks_tab.winfo_children():
            child.destroy()
        frame = ScrollFrame(self.tasks_tab)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        tasks = sorted(self.shared.current_tasks, key=lambda t: str(t.get("created_at", "")), reverse=True)
        if not tasks:
            ctk.CTkLabel(frame, text="暂无任务记录", text_color=COLORS["muted"], font=(FONT, 14)).pack(pady=32)
            return
        for t in tasks[:80]:
            status = t.get("status", "")
            color = {"completed": COLORS["success"], "failed": COLORS["danger"], "running": COLORS["accent_2"], "pending": COLORS["warning"]}.get(status, COLORS["muted"])
            row = ctk.CTkFrame(frame, fg_color=COLORS["card_2"], corner_radius=14)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=status, text_color=color, font=(FONT, 12, "bold"), width=90).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=t.get("task_name", ""), text_color=COLORS["text"], font=(FONT, 12), width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=str(t.get("created_at", ""))[:19], text_color=COLORS["muted"], font=(FONT, 12)).pack(side="right", padx=12)


def main() -> None:
    app = AppCTk()
    app.mainloop()
