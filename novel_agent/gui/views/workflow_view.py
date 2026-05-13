"""Workflow view — step navigation, dynamic form, artifact display."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable

from novel_agent.services import task_scope_from_payload

from ..step_fields import PAGE_STEP_GROUPS, STATUS_COLORS, get_step_def, get_step_label
from ..scope_utils import (
    build_base_artifact_payload,
    extract_chapter_draft_defaults,
    extract_chapter_plan_defaults,
    extract_volume_outline_defaults,
    get_artifact_for_step,
    get_dependency_states,
    get_step_readiness_message,
    get_step_status,
    get_tasks_for_step_selection,
    is_unlocked,
    selection_for_step,
)
from ..widgets.form_builder import build_form, set_field_value
from ..widgets.artifact_viewer import render_artifact_viewer
from ..theme import COLORS


class WorkflowView:
    def __init__(self, parent: tk.Widget, shared: Any):
        self.shared = shared
        self.frame = ttk.Frame(parent)
        self._form_widgets: dict = {}
        self._read_payload: Callable[[], dict] | None = None
        self._current_step: str = ""
        self._running = False

        # Three-column layout
        self.frame.grid_columnconfigure(0, weight=0)  # step nav
        self.frame.grid_columnconfigure(1, weight=2)  # form
        self.frame.grid_columnconfigure(2, weight=1)  # artifact + info
        self.frame.grid_rowconfigure(0, weight=1)

        # Left: step navigation sidebar
        self._build_step_nav()

        # Center: form area
        self._build_center()

        # Right: artifact + inspector
        self._build_right()

    def _build_step_nav(self) -> None:
        left = ttk.Frame(self.frame, width=240, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        left.grid_propagate(False)

        ttk.Label(left, text="生成步骤", style="Panel.TLabel", font=("TkDefaultFont", 14, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        ttk.Label(left, text="按依赖顺序推进作品产物", style="PanelMuted.TLabel").pack(anchor="w", padx=14, pady=(0, 10))

        canvas = tk.Canvas(left, highlightthickness=0, width=220, bg=COLORS["panel"])
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        nav_frame = ttk.Frame(canvas, style="Panel.TFrame")

        nav_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=nav_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfig("all", width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 12))
        scrollbar.pack(side="right", fill="y")

        self._step_buttons: dict[str, dict] = {}  # step_key -> {frame, label, status_label}

        for group in PAGE_STEP_GROUPS["workflow"]:
            gf = ttk.LabelFrame(nav_frame, text=group["label"], padding=6, style="Panel.TLabelframe")
            gf.pack(fill="x", padx=4, pady=(0, 8))

            for step_key in group["steps"]:
                step_def = get_step_def(step_key)
                row = ttk.Frame(gf)
                row.pack(fill="x", pady=1)

                btn = ttk.Button(
                    row,
                    text=step_def.label,
                    command=lambda sk=step_key: self._select_step(sk),
                )
                btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

                status_lbl = ttk.Label(row, text="", width=7, anchor="e")
                status_lbl.pack(side="right")

                self._step_buttons[step_key] = {"frame": row, "button": btn, "status": status_lbl}

    def _build_center(self) -> None:
        self.center = ttk.Frame(self.frame)
        self.center.grid(row=0, column=1, sticky="nsew", padx=0)
        self.center.grid_rowconfigure(1, weight=1)
        self.center.grid_columnconfigure(0, weight=1)

        # Header
        self.center_header = ttk.Frame(self.center)
        self.center_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.step_title_label = ttk.Label(self.center_header, text="选择步骤", style="Title.TLabel")
        self.step_title_label.pack(side="left")

        self.step_desc_label = ttk.Label(self.center_header, text="", style="Muted.TLabel", wraplength=620)
        self.step_desc_label.pack(side="left", padx=12)

        # Action buttons bar
        self.action_bar = ttk.Frame(self.center)
        self.action_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.generate_btn = ttk.Button(self.action_bar, text="生成", style="Accent.TButton", command=self._run_step, state="disabled")
        self.generate_btn.pack(side="left", padx=4)

        self.delete_btn = ttk.Button(self.action_bar, text="删除产物", style="Danger.TButton", command=self._delete_artifact, state="disabled")
        self.delete_btn.pack(side="left", padx=4)

        self.progress_bar = ttk.Progressbar(self.action_bar, mode="indeterminate", length=150)
        self.status_label = ttk.Label(self.action_bar, text="", style="Muted.TLabel")
        self.status_label.pack(side="right", padx=8)

        # Error / readiness message
        self.msg_label = ttk.Label(self.center, text="", foreground=COLORS["danger"], wraplength=640)
        self.msg_label.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # Form container (rebuilt per step)
        self.form_container = ttk.Frame(self.center)
        self.form_container.grid(row=1, column=0, sticky="nsew")

    def _build_right(self) -> None:
        right = ttk.Frame(self.frame, width=400)
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.grid_propagate(False)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Notebook for artifact / deps / tasks
        self.right_nb = ttk.Notebook(right)
        self.right_nb.grid(row=0, column=0, sticky="nsew")

        # Artifact tab
        self.artifact_tab = ttk.Frame(self.right_nb)
        self.right_nb.add(self.artifact_tab, text="产物")

        # Dependencies tab
        self.deps_tab = ttk.Frame(self.right_nb)
        self.right_nb.add(self.deps_tab, text="依赖检查")

        # Review checklist tab
        self.checklist_tab = ttk.Frame(self.right_nb)
        self.right_nb.add(self.checklist_tab, text="审查清单")

        # Tasks tab
        self.tasks_tab = ttk.Frame(self.right_nb)
        self.right_nb.add(self.tasks_tab, text="任务记录")

    # ------------------------------------------------------------------
    # Step selection
    # ------------------------------------------------------------------

    def _select_step(self, step_key: str) -> None:
        self._current_step = step_key
        self.shared.current_step = step_key
        self._render_step()

    def _render_step(self) -> None:
        step_key = self._current_step
        if not step_key:
            return

        step_def = get_step_def(step_key)
        self.step_title_label.configure(text=step_def.label)
        self.step_desc_label.configure(text=step_def.description)

        snapshot = self.shared.current_snapshot
        tasks = self.shared.current_tasks
        selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})

        # Readiness check
        msg = get_step_readiness_message(step_key, snapshot, selection)
        self.msg_label.configure(text=msg)

        ready = is_unlocked(step_key, snapshot, selection)
        self.generate_btn.configure(state="normal" if ready and not self._running else "disabled")

        # Clear old form
        for w in self.form_container.winfo_children():
            w.destroy()
        self._form_widgets = {}
        self._read_payload = None

        # Build new form
        form_frame, read_payload = build_form(
            self.form_container,
            step_key,
            snapshot=snapshot,
            selection=selection,
            on_ai_complete=self._on_ai_complete,
        )
        form_frame.grid(row=0, column=0, sticky="nsew")
        self.form_container.grid_rowconfigure(0, weight=1)
        self.form_container.grid_columnconfigure(0, weight=1)
        self._read_payload = read_payload

        # Hydrate defaults for scoped steps
        self._hydrate_defaults(step_key)

        # Artifact viewer
        self._render_artifact(step_key, selection)

        # Dependencies
        self._render_dependencies(step_key, selection)

        # Checklist
        self._render_checklist(step_key)

        # Tasks
        self._render_tasks(step_key, selection)

        # Delete button state
        artifact = get_artifact_for_step(snapshot, step_key, selection)
        self.delete_btn.configure(state="normal" if artifact else "disabled")

    def _hydrate_defaults(self, step_key: str) -> None:
        """Pre-fill form fields from structured artifact data."""
        snapshot = self.shared.current_snapshot
        vi = self.shared.scope.volume_index
        ci = self.shared.scope.chapter_index

        if step_key == "volume_outline":
            defaults = extract_volume_outline_defaults(snapshot, vi)
            if defaults:
                for k, v in defaults.items():
                    if v:
                        set_field_value(self._form_widgets, k, v)
        elif step_key == "chapter_plan":
            defaults = extract_chapter_plan_defaults(snapshot, vi, ci)
            if defaults:
                for k, v in defaults.items():
                    if v:
                        set_field_value(self._form_widgets, k, v)
        elif step_key == "chapter":
            defaults = extract_chapter_draft_defaults(snapshot, vi, ci)
            if defaults:
                for k, v in defaults.items():
                    if v:
                        set_field_value(self._form_widgets, k, v)

    # ------------------------------------------------------------------
    # Right panel renders
    # ------------------------------------------------------------------

    def _render_artifact(self, step_key: str, selection: dict) -> None:
        for w in self.artifact_tab.winfo_children():
            w.destroy()

        artifact = get_artifact_for_step(self.shared.current_snapshot, step_key, selection)
        viewer = render_artifact_viewer(self.artifact_tab, artifact, get_step_label(step_key))
        viewer.pack(fill="both", expand=True)

    def _render_dependencies(self, step_key: str, selection: dict) -> None:
        for w in self.deps_tab.winfo_children():
            w.destroy()

        deps = get_dependency_states(step_key, self.shared.current_snapshot, selection)
        frame = ttk.Frame(self.deps_tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        if not deps:
            ttk.Label(frame, text="此步骤无前置依赖", style="Muted.TLabel").pack()
            return

        for d in deps:
            dep_label = get_step_label(d["dependency"])
            status = d["status"]
            color = {"active": COLORS["success"], "stale": COLORS["warning"], "missing": COLORS["danger"]}.get(status, COLORS["muted"])
            status_text = {"active": "完成", "stale": "需更新", "missing": "缺失"}.get(status, status)

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=status_text, foreground=color, width=8).pack(side="left")
            ttk.Label(row, text=dep_label).pack(side="left")

    def _render_checklist(self, step_key: str) -> None:
        for w in self.checklist_tab.winfo_children():
            w.destroy()

        step_def = get_step_def(step_key)
        points = step_def.review_points
        frame = ttk.Frame(self.checklist_tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        if not points:
            ttk.Label(frame, text="无审查要点", style="Muted.TLabel").pack()
            return

        for p in points:
            ttk.Label(frame, text=f"- {p}", wraplength=330).pack(anchor="w", pady=3)

    def _render_tasks(self, step_key: str, selection: dict) -> None:
        for w in self.tasks_tab.winfo_children():
            w.destroy()

        tasks = get_tasks_for_step_selection(step_key, self.shared.current_tasks, selection)
        tasks.sort(key=lambda t: str(t.get("created_at", "")), reverse=True)

        frame = ttk.Frame(self.tasks_tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        if not tasks:
            ttk.Label(frame, text="无相关任务记录", style="Muted.TLabel").pack()
            return

        for t in tasks[:12]:
            status = t.get("status", "")
            color = {"completed": COLORS["success"], "failed": COLORS["danger"], "running": COLORS["info"], "pending": COLORS["warning"], "cancelled": COLORS["muted"]}.get(status, COLORS["muted"])

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=status, foreground=color, width=8).pack(side="left")
            created = str(t.get("created_at", ""))[:19]
            ttk.Label(row, text=created, style="Muted.TLabel").pack(side="right")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _run_step(self) -> None:
        if not self._read_payload or self._running:
            return

        step_key = self._current_step
        selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})

        # Check readiness
        if not is_unlocked(step_key, self.shared.current_snapshot, selection):
            msg = get_step_readiness_message(step_key, self.shared.current_snapshot, selection)
            messagebox.showwarning("依赖未就绪", msg)
            return

        # Read payload
        payload = self._read_payload()

        # Attach base artifact for scoped steps
        base = build_base_artifact_payload(step_key, self.shared.current_snapshot, selection)
        if base:
            payload["base_artifact"] = base

        # Submit task
        self._running = True
        self.generate_btn.configure(state="disabled")
        self.progress_bar.pack(side="right", padx=8)
        self.progress_bar.start(10)
        self.status_label.configure(text="生成中...")

        try:
            scope = task_scope_from_payload(step_key, payload)

            def _job() -> Any:
                result = self.shared.container.orchestrator.dispatch(
                    self.shared.current_project_id, step_key, payload
                )
                return result.model_dump(mode="json")

            task = self.shared.container.task_service.submit(
                project_id=self.shared.current_project_id,
                task_name=step_key,
                job=_job,
                scope=scope,
                input_payload=payload,
            )

            self.shared.task_monitor.start(
                task.task_id,
                on_complete=self._on_task_complete,
                on_error=self._on_task_error,
            )
        except Exception as e:
            self._running = False
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.status_label.configure(text="")
            self.generate_btn.configure(state="normal")
            messagebox.showerror("提交失败", str(e))

    def _on_task_complete(self, task: dict) -> None:
        self._running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.status_label.configure(text="完成 ✓")
        self.generate_btn.configure(state="normal")
        self._refresh_after_task()

    def _on_task_error(self, task: dict | None) -> None:
        self._running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.status_label.configure(text="")
        self.generate_btn.configure(state="normal")

        error_msg = "任务失败"
        if task:
            error_msg = task.get("error", "任务执行失败")
        messagebox.showerror("执行失败", error_msg)
        self._refresh_after_task()

    def _refresh_after_task(self) -> None:
        """Reload snapshot and tasks, re-render current step."""
        try:
            snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_snapshot = snapshot
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
        except Exception:
            pass
        self._render_step()
        self._refresh_step_nav_statuses()

    def _on_ai_complete(self, field_key: str, payload: dict) -> None:
        """Handle AI field completion request."""
        step_key = self._current_step
        step_def = get_step_def(step_key)

        field = next((f for f in step_def.fields if f.key == field_key), None)
        if not field:
            return

        # Run LLM completion in background thread
        def _run() -> None:
            try:
                result = self.shared.container.llm_service.complete(
                    prompt=f"为以下小说创作步骤的字段 '{field.label}' 提供建议值：\n\n步骤：{step_def.label}\n描述：{step_def.description}\n字段：{field.label}\n当前上下文：{payload}\n\n请直接输出建议的字段值，不要额外说明。",
                    system_prompt="你是小说创作助手。根据上下文给出简洁、具体的字段建议。",
                    temperature=0.7,
                    max_tokens=300,
                    metadata={"step": step_key, "field": field_key},
                )
                value = result.strip() if isinstance(result, str) else ""
                self.frame.after(0, lambda v=value: set_field_value(self._form_widgets, field_key, v))
            except Exception as e:
                self.frame.after(0, lambda e_msg=str(e): messagebox.showerror("AI补全失败", e_msg))

        threading.Thread(target=_run, daemon=True).start()

    def _delete_artifact(self) -> None:
        step_key = self._current_step
        selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
        artifact = get_artifact_for_step(self.shared.current_snapshot, step_key, selection)
        if not artifact:
            return

        artifact_key = artifact.get("key", "")
        ok = messagebox.askyesno("确认删除", f"删除产物 '{artifact_key}' 将级联清理下游产物，确定继续？")
        if not ok:
            return

        try:
            self.shared.container.project_service.remove_artifact(self.shared.current_project_id, artifact_key)
            self._refresh_after_task()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def _refresh_step_nav_statuses(self) -> None:
        """Update status indicators on step navigation buttons."""
        snapshot = self.shared.current_snapshot
        tasks = self.shared.current_tasks

        for step_key, btns in self._step_buttons.items():
            selection = selection_for_step(step_key, {"volume_index": self.shared.scope.volume_index, "chapter_index": self.shared.scope.chapter_index})
            status = get_step_status(step_key, snapshot, tasks, selection)
            btns["status"].configure(text=status["text"], foreground=STATUS_COLORS.get(status["tone"], COLORS["muted"]))

    def refresh(self) -> None:
        """Called when view becomes visible."""
        if self.shared.current_project_id:
            try:
                snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
                tasks = self.shared.container.task_service.list(self.shared.current_project_id)
                self.shared.current_snapshot = snapshot
                self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
            except Exception:
                pass
        self._refresh_step_nav_statuses()
        if self._current_step:
            self._render_step()
