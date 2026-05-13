"""Project hub view — list, create, edit, delete projects."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable

from novel_agent.domain import ProjectInput
from ..theme import COLORS, style_listbox, style_text_widget


def _w_has_var(wtype: str) -> bool:
    return wtype in ("text", "number")


def _w_is_text_widget(wtype: str) -> bool:
    return wtype in ("textarea", "list")


def _w_get(wdata: dict) -> str:
    if _w_has_var(wdata["type"]):
        return wdata["var"].get()
    return wdata["widget"].get("1.0", "end-1c")


def _w_set(wdata: dict, value: Any) -> None:
    if _w_has_var(wdata["type"]):
        wdata["var"].set(str(value if value is not None else ""))
    else:
        w = wdata["widget"]
        w.delete("1.0", "end")
        if isinstance(value, list):
            w.insert("1.0", "\n".join(str(x) for x in value))
        elif value:
            w.insert("1.0", str(value))


def _w_clear(wdata: dict) -> None:
    if _w_has_var(wdata["type"]):
        wdata["var"].set("")
    else:
        wdata["widget"].delete("1.0", "end")


class ProjectHubView:
    def __init__(self, parent: tk.Widget, shared: Any, switch_view: Callable[[str], None]):
        self.shared = shared
        self.switch_view = switch_view

        self.frame = ttk.Frame(parent, style="AppShell.TFrame")
        self.frame.grid_columnconfigure(1, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)

        # Left: project list
        self.left = ttk.Frame(self.frame, width=360, style="Panel.TFrame")
        self.left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self.left.grid_propagate(False)

        header = ttk.Frame(self.left, style="Panel.TFrame")
        header.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(header, text="作品库", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(header, text="选择作品后进入生成工作流", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 0))

        # Stats row
        self.stats_frame = ttk.Frame(self.left, style="Panel.TFrame")
        self.stats_frame.pack(fill="x", padx=14, pady=(0, 12))
        self.stat_labels: dict[str, ttk.Label] = {}

        # Project listbox
        list_frame = ttk.Frame(self.left, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 16))

        self.project_listbox = tk.Listbox(list_frame, exportselection=False)
        style_listbox(self.project_listbox)
        self.project_listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.project_listbox.yview)
        self.project_listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.project_listbox.bind("<<ListboxSelect>>", self._on_select)

        # Right: create/edit form
        self.right = ttk.Frame(self.frame, style="AppShell.TFrame")
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        hero = ttk.Frame(self.right, style="Hero.TFrame")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(hero, text="作品蓝图", style="HeroTitle.TLabel").pack(anchor="w", padx=18, pady=(16, 2))
        ttk.Label(
            hero,
            text="先把题材、前提、规模和风格约束整理清楚，后续生成步骤会围绕这些全局设定展开。",
            style="HeroMuted.TLabel",
            wraplength=760,
        ).pack(anchor="w", padx=18, pady=(0, 16))

        # Scrollable form
        form_shell = ttk.Frame(self.right, style="Panel.TFrame")
        form_shell.grid(row=1, column=0, sticky="nsew")
        form_shell.grid_rowconfigure(0, weight=1)
        form_shell.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(form_shell, highlightthickness=0, bg=COLORS["panel"])
        form_scroll = ttk.Scrollbar(form_shell, orient="vertical", command=canvas.yview)
        self.form_frame = ttk.Frame(canvas, style="Panel.TFrame")

        self.form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        canvas.configure(yscrollcommand=form_scroll.set)

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfig("all", width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        form_scroll.grid(row=0, column=1, sticky="ns", pady=14)

        # Build form sections
        self._widgets: dict[str, dict] = {}
        self._build_form()

        # Action buttons
        btn_frame = ttk.Frame(self.right, style="AppShell.TFrame")
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        self.create_btn = ttk.Button(btn_frame, text="＋ 创建项目", style="Accent.TButton", command=self._create_project)
        self.create_btn.pack(side="left", padx=(0, 8))

        self.update_btn = ttk.Button(btn_frame, text="保存修改", command=self._update_project, state="disabled")
        self.update_btn.pack(side="left", padx=4)

        self.delete_btn = ttk.Button(btn_frame, text="删除", style="Danger.TButton", command=self._delete_project, state="disabled")
        self.delete_btn.pack(side="left", padx=4)

        self.open_workflow_btn = ttk.Button(btn_frame, text="进入创作工作台 →", style="Accent.TButton", command=lambda: self.switch_view("workflow"), state="disabled")
        self.open_workflow_btn.pack(side="right")

        self._project_ids: list[str] = []

    def _build_form(self) -> None:
        sections = [
            ("作品定位", "一句话讲清楚这部作品是什么。", [
                ("title", "作品标题", "text", None),
                ("genre", "作品类型", "text", None),
                ("premise", "前提/核心构思", "textarea", 4),
                ("target_audience", "目标受众", "text", None),
            ]),
            ("规模与节奏", "控制整体篇幅、卷章结构和推进颗粒度。", [
                ("target_words", "目标总字数", "number", None),
                ("target_volume_count", "目标卷数", "number", None),
                ("target_chapters_per_volume", "每卷章节数", "number", None),
            ]),
            ("风格与约束", "一行一个标签，越具体越容易稳定生成。", [
                ("tone", "基调标签（一行一个）", "list", 4),
                ("style", "风格标签（一行一个）", "list", 4),
                ("outline_focus", "总纲关注点（一行一个）", "list", 4),
                ("core_requirements", "核心要求（一行一个）", "list", 4),
                ("forbidden_elements", "禁忌元素（一行一个）", "list", 4),
            ]),
        ]

        row = 0
        for section_title, section_hint, fields in sections:
            card = ttk.Frame(self.form_frame, style="Card.TFrame")
            card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)
            inner = ttk.Frame(card, style="Card.TFrame")
            inner.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
            inner.grid_columnconfigure(1, weight=1)

            ttk.Label(inner, text=section_title, style="Card.TLabel", font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
            ttk.Label(inner, text=section_hint, style="CardMuted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))

            for i, (key, label, ftype, rows) in enumerate(fields, start=2):
                ttk.Label(inner, text=label, style="CardMuted.TLabel").grid(row=i, column=0, sticky="nw", padx=(0, 16), pady=7)

                if ftype == "textarea":
                    w = tk.Text(inner, height=rows or 3, width=40, wrap="word")
                    style_text_widget(w)
                    w.grid(row=i, column=1, sticky="ew", pady=7)
                    self._widgets[key] = {"widget": w, "type": "textarea"}
                elif ftype == "list":
                    w = tk.Text(inner, height=rows or 3, width=40, wrap="word")
                    style_text_widget(w)
                    w.grid(row=i, column=1, sticky="ew", pady=7)
                    self._widgets[key] = {"widget": w, "type": "list"}
                elif ftype == "number":
                    var = tk.StringVar(value="")
                    w = ttk.Spinbox(inner, textvariable=var, from_=0, to=9999999)
                    w.grid(row=i, column=1, sticky="ew", pady=7)
                    self._widgets[key] = {"widget": w, "type": "number", "var": var}
                else:
                    var = tk.StringVar(value="")
                    w = ttk.Entry(inner, textvariable=var)
                    w.grid(row=i, column=1, sticky="ew", pady=7)
                    self._widgets[key] = {"widget": w, "type": "text", "var": var}

            row += 1

    def _read_payload(self) -> dict:
        payload: dict = {}
        for key, wdata in self._widgets.items():
            wtype = wdata["type"]
            value = _w_get(wdata)
            if wtype == "list":
                payload[key] = [line.strip() for line in value.splitlines() if line.strip()]
            else:
                payload[key] = value
        return payload

    def _fill_form(self, project: dict) -> None:
        pi = project.get("input", {}) or {}
        for key, wdata in self._widgets.items():
            val = pi.get(key)
            _w_set(wdata, val)

    def _clear_form(self) -> None:
        for wdata in self._widgets.values():
            _w_clear(wdata)

    def _create_project(self) -> None:
        payload = self._read_payload()
        if not payload.get("title") or not payload.get("genre"):
            messagebox.showwarning("缺少信息", "作品标题和类型为必填项。")
            return

        try:
            for k in ("target_words", "target_volume_count", "target_chapters_per_volume"):
                if payload.get(k):
                    try:
                        payload[k] = int(payload[k])
                    except (ValueError, TypeError):
                        payload[k] = 0

            project_input = ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])})
            project = self.shared.container.orchestrator.create_project(project_input)
            self.shared.current_project_id = project.project_id
            self.refresh()
            messagebox.showinfo("成功", f"项目 '{project.input.title}' 创建成功。")
        except Exception as e:
            messagebox.showerror("创建失败", str(e))

    def _update_project(self) -> None:
        if not self.shared.current_project_id:
            return
        payload = self._read_payload()
        if not payload.get("title") or not payload.get("genre"):
            messagebox.showwarning("缺少信息", "作品标题和类型为必填项。")
            return

        ok = messagebox.askyesno("确认更新", "更新项目将清除所有已有产物和历史记录，确定继续？")
        if not ok:
            return

        try:
            for k in ("target_words", "target_volume_count", "target_chapters_per_volume"):
                if payload.get(k):
                    try:
                        payload[k] = int(payload[k])
                    except (ValueError, TypeError):
                        payload[k] = 0

            project_input = ProjectInput(**{k: v for k, v in payload.items() if v not in (None, "", [])})
            project = self.shared.container.orchestrator.update_project(self.shared.current_project_id, project_input)
            self.refresh()
            messagebox.showinfo("成功", "项目已更新，所有产物已清除。")
        except Exception as e:
            messagebox.showerror("更新失败", str(e))

    def _delete_project(self) -> None:
        if not self.shared.current_project_id:
            return
        ok = messagebox.askyesno("确认删除", "删除操作不可撤销，确定要删除此项目吗？")
        if not ok:
            return

        try:
            pid = self.shared.current_project_id
            self.shared.container.task_service.delete_project(pid)
            self.shared.container.project_service.delete(pid)
            self.shared.current_project_id = ""
            self.shared.current_snapshot = None
            self.shared.current_tasks = []
            self.refresh()
            messagebox.showinfo("成功", "项目已删除。")
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def _on_select(self, event: tk.Event) -> None:
        sel = self.project_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._project_ids):
            pid = self._project_ids[idx]
            self.shared.current_project_id = pid
            self._load_snapshot()

    def refresh(self) -> None:
        """Reload project list and stats."""
        try:
            projects = self.shared.container.orchestrator.list_projects()
        except Exception:
            projects = []

        self._project_ids = []
        self.project_listbox.delete(0, "end")

        for p in projects:
            pi = p.input if hasattr(p, "input") else p.get("input", {})
            title = pi.title if hasattr(pi, "title") else pi.get("title", "未命名")
            status = ""
            if hasattr(p, "status"):
                status = str(p.status.value if hasattr(p.status, "value") else p.status)
            label = f"  {title}"
            if status:
                label += f"    · {status}"
            self.project_listbox.insert("end", label)
            self._project_ids.append(p.project_id if hasattr(p, "project_id") else p.get("project_id", ""))

        # Stats
        for w in self.stats_frame.winfo_children():
            w.destroy()

        stats = [
            ("项目", str(len(projects))),
            ("当前", "已选择" if self.shared.current_project_id else "未选择"),
        ]
        for i, (label, value) in enumerate(stats):
            card = ttk.Frame(self.stats_frame, style="Card.TFrame")
            card.grid(row=0, column=i, sticky="ew", padx=4)
            ttk.Label(card, text=value, style="StatValue.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
            ttk.Label(card, text=label, style="StatLabel.TLabel").pack(anchor="w", padx=12, pady=(0, 10))
            self.stats_frame.grid_columnconfigure(i, weight=1)

        # Select current
        if self.shared.current_project_id:
            try:
                idx = self._project_ids.index(self.shared.current_project_id)
                self.project_listbox.selection_set(idx)
                self.project_listbox.see(idx)
                self._load_snapshot()
            except ValueError:
                self._clear_form()
                self.update_btn.configure(state="disabled")
                self.delete_btn.configure(state="disabled")
                self.open_workflow_btn.configure(state="disabled")
        else:
            self._clear_form()
            self.update_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
            self.open_workflow_btn.configure(state="disabled")

    def _load_snapshot(self) -> None:
        if not self.shared.current_project_id:
            return
        try:
            snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_snapshot = snapshot
            self.shared.current_tasks = tasks
            project = snapshot.get("project", {})
            self._fill_form(project)
            self.update_btn.configure(state="normal")
            self.delete_btn.configure(state="normal")
            self.open_workflow_btn.configure(state="normal")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
