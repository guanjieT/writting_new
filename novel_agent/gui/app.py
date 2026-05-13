"""GUI application shell — Tk root, container init, sidebar nav, page switching."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from novel_agent.config import load_config
from novel_agent.container import build_container

from .state import AppShared
from .task_monitor import TaskMonitor
from .scope_utils import (
    get_chapter_entry_options,
    get_volume_entry_options,
)
from .views.project_view import ProjectHubView
from .views.workflow_view import WorkflowView
from .views.review_view import ReviewView
from .theme import apply_theme


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Novel Agent — 小说创作助手")
        root.geometry("1400x900")
        root.minsize(1000, 600)

        apply_theme(root)

        # Load config and build DI container
        config = load_config()
        self.container = build_container(config)

        # Shared state
        self.shared = AppShared(
            container=self.container,
            task_monitor=TaskMonitor(root, self.container.task_service),
        )

        # Build UI
        self._build_menu()
        self._build_layout()

        # Start with project hub
        self.switch_view("project")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="项目中心", command=lambda: self.switch_view("project"))
        file_menu.add_command(label="工作台", command=lambda: self.switch_view("workflow"))
        file_menu.add_command(label="审查面板", command=lambda: self.switch_view("review"))
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

    def _build_layout(self) -> None:
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ttk.Frame(self.main_frame, width=260, style="Sidebar.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.pack(fill="x", padx=16, pady=(18, 14))
        ttk.Label(brand, text="Novel Agent", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(brand, text="结构化小说创作工作台", style="SidebarMuted.TLabel").pack(anchor="w", pady=(4, 0))

        # Project info
        proj_frame = ttk.LabelFrame(sidebar, text="当前项目", padding=10, style="Sidebar.TLabelframe")
        proj_frame.pack(fill="x", padx=14, pady=(0, 12))

        self.project_name_label = ttk.Label(proj_frame, text="（未选择）", wraplength=210, style="SidebarValue.TLabel", font=("TkDefaultFont", 11, "bold"))
        self.project_name_label.pack(anchor="w")
        self.project_genre_label = ttk.Label(proj_frame, text="", style="SidebarMuted.TLabel")
        self.project_genre_label.pack(anchor="w")
        self.project_status_label = ttk.Label(proj_frame, text="", style="SidebarMuted.TLabel")
        self.project_status_label.pack(anchor="w")

        # Navigation buttons
        nav_frame = ttk.LabelFrame(sidebar, text="导航", padding=8, style="Sidebar.TLabelframe")
        nav_frame.pack(fill="x", padx=14, pady=(0, 12))

        self.nav_project_btn = ttk.Button(nav_frame, text="项目中心", style="Nav.TButton", command=lambda: self.switch_view("project"))
        self.nav_project_btn.pack(fill="x", pady=3)

        self.nav_workflow_btn = ttk.Button(nav_frame, text="工作台", style="Nav.TButton", command=lambda: self.switch_view("workflow"))
        self.nav_workflow_btn.pack(fill="x", pady=3)

        self.nav_review_btn = ttk.Button(nav_frame, text="审查面板", style="Nav.TButton", command=lambda: self.switch_view("review"))
        self.nav_review_btn.pack(fill="x", pady=3)

        # Scope selection
        scope_frame = ttk.LabelFrame(sidebar, text="范围选择", padding=10, style="Sidebar.TLabelframe")
        scope_frame.pack(fill="x", padx=14, pady=(0, 12))

        ttk.Label(scope_frame, text="卷", style="SidebarMuted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.volume_combo = ttk.Combobox(scope_frame, state="readonly", width=12)
        self.volume_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.volume_combo.bind("<<ComboboxSelected>>", self._on_scope_change)

        ttk.Label(scope_frame, text="章", style="SidebarMuted.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.chapter_combo = ttk.Combobox(scope_frame, state="readonly", width=12)
        self.chapter_combo.grid(row=1, column=1, sticky="ew", pady=2)
        self.chapter_combo.bind("<<ComboboxSelected>>", self._on_scope_change)

        scope_frame.grid_columnconfigure(1, weight=1)

        # Task status indicator
        task_box = ttk.Frame(sidebar, style="Sidebar.TFrame")
        task_box.pack(side="bottom", fill="x", padx=16, pady=18)
        self.task_indicator = ttk.Label(task_box, text="", style="SidebarMuted.TLabel")
        self.task_indicator.pack(anchor="w")

        # Content panel
        self.content_panel = ttk.Frame(self.main_frame)
        self.content_panel.pack(side="left", fill="both", expand=True, padx=14, pady=14)

        # Build views
        self._views: dict[str, Any] = {
            "project": ProjectHubView(self.content_panel, self.shared, self.switch_view),
            "workflow": WorkflowView(self.content_panel, self.shared),
            "review": ReviewView(self.content_panel, self.shared),
        }

        # Status bar
        status_bar = ttk.Frame(self.root, style="Status.TFrame")
        status_bar.pack(side="bottom", fill="x")

        self.status_label = ttk.Label(status_bar, text="就绪", style="PanelMuted.TLabel")
        self.status_label.pack(side="left", padx=12, pady=4)

        self.running_indicator = ttk.Progressbar(status_bar, mode="indeterminate", length=120)
        # Start hidden

    def switch_view(self, view_name: str) -> None:
        """Show one view, hide the others."""
        for name, view in self._views.items():
            if name == view_name:
                view.frame.pack(fill="both", expand=True)
            else:
                view.frame.pack_forget()

        self._current_view = view_name

        # Update nav button styles
        for name, btn in [
            ("project", self.nav_project_btn),
            ("workflow", self.nav_workflow_btn),
            ("review", self.nav_review_btn),
        ]:
            if name == view_name:
                btn.configure(style="NavSelected.TButton")
            else:
                btn.configure(style="Nav.TButton")

        # Refresh view (workflow and review require a selected project)
        if view_name in ("workflow", "review") and not self.shared.current_project_id:
            messagebox.showwarning("未选择项目", "请先在项目中心选择或创建一个项目。")
            self.switch_view("project")
            return

        view = self._views[view_name]
        if hasattr(view, "refresh"):
            view.refresh()

        self._refresh_scope_combos()
        self._refresh_project_info()

    def _on_scope_change(self, event: tk.Event | None = None) -> None:
        """Handle volume/chapter combobox selection change."""
        vol_val = self.volume_combo.get()
        ch_val = self.chapter_combo.get()

        # Parse volume index
        for opt in get_volume_entry_options(self.shared.current_snapshot):
            if opt["label"] == vol_val:
                try:
                    self.shared.scope.volume_index = int(opt["value"])
                except (ValueError, TypeError):
                    pass
                break

        # Parse chapter index
        for opt in get_chapter_entry_options(self.shared.current_snapshot, self.shared.scope.volume_index):
            if opt["label"] == ch_val:
                try:
                    self.shared.scope.chapter_index = int(opt["value"])
                except (ValueError, TypeError):
                    pass
                break

        # Refresh current view
        if self._current_view in ("workflow", "review"):
            view = self._views[self._current_view]
            if hasattr(view, "refresh"):
                view.refresh()

    def _refresh_scope_combos(self) -> None:
        """Populate volume/chapter comboboxes from snapshot data."""
        snapshot = self.shared.current_snapshot

        # Volume combobox
        vol_options = get_volume_entry_options(snapshot)
        vol_labels = [o["label"] for o in vol_options]
        self.volume_combo["values"] = vol_labels

        if vol_options:
            # Try to keep current selection
            current_vol = str(self.shared.scope.volume_index)
            found = False
            for o in vol_options:
                if o["value"] == current_vol:
                    self.volume_combo.set(o["label"])
                    found = True
                    break
            if not found:
                self.volume_combo.set(vol_labels[0])
                try:
                    self.shared.scope.volume_index = int(vol_options[0]["value"])
                except (ValueError, TypeError):
                    pass
        else:
            self.volume_combo.set("")
            self.volume_combo["values"] = ["第 1 卷 (默认)"]
            self.volume_combo.set("第 1 卷 (默认)")

        # Chapter combobox
        ch_options = get_chapter_entry_options(snapshot, self.shared.scope.volume_index)
        ch_labels = [o["label"] for o in ch_options]
        self.chapter_combo["values"] = ch_labels

        if ch_options:
            current_ch = str(self.shared.scope.chapter_index)
            found = False
            for o in ch_options:
                if o["value"] == current_ch:
                    self.chapter_combo.set(o["label"])
                    found = True
                    break
            if not found:
                self.chapter_combo.set(ch_labels[0])
                try:
                    self.shared.scope.chapter_index = int(ch_options[0]["value"])
                except (ValueError, TypeError):
                    pass
        else:
            self.chapter_combo["values"] = ["第 1 章 (默认)"]
            self.chapter_combo.set("第 1 章 (默认)")

    def _refresh_project_info(self) -> None:
        """Update project info in sidebar."""
        project = self.shared.project()
        if project:
            pi = project.get("input", {}) or {}
            self.project_name_label.configure(text=pi.get("title", "未命名"))
            self.project_genre_label.configure(text=pi.get("genre", ""))
            status = project.get("status", "")
            if hasattr(status, "value"):
                status = status.value
            self.project_status_label.configure(text=f"状态: {status}")
        else:
            self.project_name_label.configure(text="（未选择）")
            self.project_genre_label.configure(text="")
            self.project_status_label.configure(text="")

        # Update task indicator
        active = self.shared.task_monitor.active_count
        if active > 0:
            self.task_indicator.configure(text=f"运行中: {active} 个任务", foreground="#bfdbfe")
        else:
            self.task_indicator.configure(text="无运行任务", foreground="#b8c2d4")

    def _show_about(self) -> None:
        messagebox.showinfo("关于", "Novel Agent Clean\n小说创作助手\n\n一个结构化的 AI 辅助小说创作系统。")
