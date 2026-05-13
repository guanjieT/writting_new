"""Review view — quality report, progress matrix, task history."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from ..step_fields import REVIEW_GROUPS, STATUS_COLORS, get_step_def, get_step_label
from ..scope_utils import (
    artifact_is_stale,
    get_artifact_for_step,
    get_step_status,
    selection_for_step,
)
from ..theme import COLORS, style_text_widget


class ReviewView:
    def __init__(self, parent: tk.Widget, shared: Any):
        self.shared = shared
        self.frame = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(self.frame)
        hdr.pack(fill="x", pady=(0, 10))
        ttk.Label(hdr, text="审查面板", style="Title.TLabel").pack(side="left")
        ttk.Label(hdr, text="查看产物状态、任务历史和质量阻塞项", style="Muted.TLabel").pack(side="left", padx=12)

        self.refresh_btn = ttk.Button(hdr, text="刷新", command=self.refresh)
        self.refresh_btn.pack(side="right")

        # Notebook for sections
        nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True)

        # Summary tab
        self.summary_tab = ttk.Frame(nb)
        nb.add(self.summary_tab, text="总览")

        # Matrix tab
        self.matrix_tab = ttk.Frame(nb)
        nb.add(self.matrix_tab, text="进度矩阵")

        # Tasks tab
        self.tasks_tab = ttk.Frame(nb)
        nb.add(self.tasks_tab, text="全部任务")

        # Quality tab
        self.quality_tab = ttk.Frame(nb)
        nb.add(self.quality_tab, text="质量报告")

    def refresh(self) -> None:
        if not self.shared.current_project_id:
            return

        try:
            snapshot = self.shared.container.orchestrator.project_snapshot(self.shared.current_project_id)
            tasks = self.shared.container.task_service.list(self.shared.current_project_id)
            self.shared.current_snapshot = snapshot
            self.shared.current_tasks = [t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in tasks]
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
            return

        self._render_summary()
        self._render_matrix()
        self._render_tasks()
        self._render_quality()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _render_summary(self) -> None:
        for w in self.summary_tab.winfo_children():
            w.destroy()

        snapshot = self.shared.current_snapshot or {}
        project = snapshot.get("project", {}) or {}
        pi = project.get("input", {}) or {}
        artifacts = snapshot.get("artifacts", {}) or {}

        # Stats
        stats_frame = ttk.Frame(self.summary_tab)
        stats_frame.pack(fill="x", padx=8, pady=12)

        total = 12
        active = sum(1 for a in artifacts.values() if not artifact_is_stale(a))
        stale = sum(1 for a in artifacts.values() if artifact_is_stale(a))
        tasks = self.shared.current_tasks
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")
        running_tasks = sum(1 for t in tasks if t.get("status") in ("running", "pending"))

        stats = [
            ("总步骤", str(total)),
            ("已产出", str(active)),
            ("已失效", str(stale)),
            ("失败任务", str(failed_tasks)),
            ("进行中", str(running_tasks)),
        ]

        for i, (label, value) in enumerate(stats):
            card = ttk.Frame(stats_frame, style="Card.TFrame")
            card.grid(row=0, column=i, sticky="ew", padx=6, pady=4)
            ttk.Label(card, text=value, style="Panel.TLabel", font=("TkDefaultFont", 20, "bold")).pack(padx=18, pady=(12, 0))
            ttk.Label(card, text=label, style="PanelMuted.TLabel").pack(padx=18, pady=(0, 12))
            stats_frame.grid_columnconfigure(i, weight=1)

        # Project info
        info_frame = ttk.LabelFrame(self.summary_tab, text="项目信息", padding=10)
        info_frame.pack(fill="x", padx=8, pady=4)

        fields = [
            ("标题", pi.get("title", "未知")),
            ("类型", pi.get("genre", "未知")),
            ("目标字数", f"{pi.get('target_words', 0):,}"),
            ("卷/章", f"{pi.get('target_volume_count', 1)} 卷 × {pi.get('target_chapters_per_volume', 12)} 章"),
            ("前提", str(pi.get("premise", "") or "（未设置）")[:120]),
        ]
        for i, (label, value) in enumerate(fields):
            row = ttk.Frame(info_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{label}: ", style="Muted.TLabel", width=10, anchor="e").pack(side="left")
            ttk.Label(row, text=str(value), wraplength=500).pack(side="left", padx=4)

        # Progress bar
        completion_ratio = active / total if total > 0 else 0
        progress_frame = ttk.Frame(self.summary_tab)
        progress_frame.pack(fill="x", padx=8, pady=8)
        ttk.Label(progress_frame, text=f"完成度: {completion_ratio:.0%}").pack(anchor="w")
        bar = ttk.Progressbar(progress_frame, value=completion_ratio * 100)
        bar.pack(fill="x", pady=4)

        # Knowledge base
        kb = project.get("knowledge_base", []) or []
        if kb:
            kb_frame = ttk.LabelFrame(self.summary_tab, text=f"知识库 ({len(kb)} 条)", padding=8)
            kb_frame.pack(fill="both", expand=True, padx=8, pady=4)

            kb_text = tk.Text(kb_frame, height=6, wrap="word", state="normal")
            style_text_widget(kb_text)
            kb_scroll = ttk.Scrollbar(kb_frame, orient="vertical", command=kb_text.yview)
            kb_text.configure(yscrollcommand=kb_scroll.set)

            for item in kb[:50]:
                kind = item.get("kind", "")
                text = str(item.get("text", ""))
                source = item.get("source_step", "")
                kb_text.insert("end", f"[{kind}] {text}")
                if source:
                    kb_text.insert("end", f"  (来源: {source})")
                kb_text.insert("end", "\n")

            kb_text.configure(state="disabled")
            kb_text.pack(side="left", fill="both", expand=True)
            kb_scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Progress Matrix
    # ------------------------------------------------------------------

    def _render_matrix(self) -> None:
        for w in self.matrix_tab.winfo_children():
            w.destroy()

        snapshot = self.shared.current_snapshot
        tasks = self.shared.current_tasks

        # Treeview: step | status | scope | artifact key | content preview
        frame = ttk.Frame(self.matrix_tab)
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        tree = ttk.Treeview(
            frame,
            columns=("status", "scope", "key", "content"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("status", text="状态")
        tree.heading("scope", text="范围")
        tree.heading("key", text="产物键")
        tree.heading("content", text="内容预览")

        tree.column("status", width=80, anchor="center")
        tree.column("scope", width=100)
        tree.column("key", width=200)
        tree.column("content", width=300)

        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Populate by groups
        for group in REVIEW_GROUPS:
            group_id = tree.insert("", "end", text=group["label"], values=("", "", "", ""), open=True)
            for step_key in group["steps"]:
                selection = selection_for_step(step_key, {
                    "volume_index": self.shared.scope.volume_index,
                    "chapter_index": self.shared.scope.chapter_index,
                })
                status = get_step_status(step_key, snapshot, tasks, selection)
                artifact = get_artifact_for_step(snapshot, step_key, selection)

                scope_text = "全书"
                sel = selection
                if sel.get("chapter_index"):
                    scope_text = f"第{sel['volume_index']}卷第{sel['chapter_index']}章"
                elif sel.get("volume_index"):
                    scope_text = f"第{sel['volume_index']}卷"

                key_text = artifact.get("key", "") if artifact else "—"
                content_text = ""
                if artifact:
                    content = str(artifact.get("content", "") or "")
                    content_text = content[:100].replace("\n", " ")

                tree.insert(
                    group_id, "end",
                    text=get_step_label(step_key),
                    values=(status["text"], scope_text, key_text, content_text),
                    tags=(status["tone"],),
                )

        for tone, color in STATUS_COLORS.items():
            tree.tag_configure(tone, foreground=color)

    # ------------------------------------------------------------------
    # All Tasks
    # ------------------------------------------------------------------

    def _render_tasks(self) -> None:
        for w in self.tasks_tab.winfo_children():
            w.destroy()

        tasks = self.shared.current_tasks
        tasks_sorted = sorted(tasks, key=lambda t: str(t.get("created_at", "")), reverse=True)

        frame = ttk.Frame(self.tasks_tab)
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        tree = ttk.Treeview(
            frame,
            columns=("status", "name", "scope", "time", "error"),
            show="headings",
        )
        tree.heading("status", text="状态")
        tree.heading("name", text="任务")
        tree.heading("scope", text="范围")
        tree.heading("time", text="时间")
        tree.heading("error", text="错误信息")

        tree.column("status", width=70, anchor="center")
        tree.column("name", width=100)
        tree.column("scope", width=100)
        tree.column("time", width=150)
        tree.column("error", width=250)

        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        for t in tasks_sorted[:50]:
            status = t.get("status", "")
            name = t.get("task_name", "")
            scope_kind = t.get("scope_kind", "project")
            vi = t.get("volume_index", "")
            ci = t.get("chapter_index", "")
            scope_text = scope_kind
            if scope_kind == "volume":
                scope_text = f"第{vi}卷"
            elif scope_kind == "chapter":
                scope_text = f"第{vi}卷第{ci}章"

            created = str(t.get("created_at", ""))[:19]
            error = str(t.get("error", "") or "")[:100]

            color = {"completed": COLORS["success"], "failed": COLORS["danger"], "running": COLORS["info"], "pending": COLORS["warning"], "cancelled": COLORS["muted"]}.get(status, COLORS["muted"])

            item = tree.insert("", "end", text="", values=(status, name, scope_text, created, error))
            tree.item(item, tags=(status,))
            tree.tag_configure(status, foreground=color)

    # ------------------------------------------------------------------
    # Quality Report
    # ------------------------------------------------------------------

    def _render_quality(self) -> None:
        for w in self.quality_tab.winfo_children():
            w.destroy()

        try:
            from novel_agent.quality import build_quality_report

            project = self.shared.container.orchestrator.get_project(self.shared.current_project_id)
            report = build_quality_report(project)
        except Exception:
            report = None

        if not report:
            ttk.Label(self.quality_tab, text="暂无质量数据", style="Muted.TLabel").pack(padx=12, pady=24)
            return

        frame = ttk.Frame(self.quality_tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Summary
        ttk.Label(frame, text="质量报告", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        summary_frame = ttk.Frame(frame)
        summary_frame.pack(fill="x", pady=4)
        ttk.Label(summary_frame, text=f"检查章节数: {report.get('checked_chapters', 0)}").pack(side="left", padx=8)
        ttk.Label(summary_frame, text=f"阻塞问题: {report.get('blocking_issue_count', 0)}").pack(side="left", padx=8)
        ready = "是" if report.get("ready_for_export") else "否"
        ttk.Label(summary_frame, text=f"可导出: {ready}", foreground=COLORS["success"] if report.get("ready_for_export") else COLORS["danger"]).pack(side="left", padx=8)

        # Chapters table
        chapters = report.get("chapters", []) or []
        if not chapters:
            ttk.Label(frame, text="暂无章节数据", style="Muted.TLabel").pack(pady=8)
            return

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True, pady=8)

        tree = ttk.Treeview(
            tree_frame,
            columns=("target", "actual", "revision", "consistency", "memory", "issues"),
            show="headings",
        )
        tree.heading("target", text="目标字数")
        tree.heading("actual", text="实际字数")
        tree.heading("revision", text="修订")
        tree.heading("consistency", text="一致性")
        tree.heading("memory", text="记忆")
        tree.heading("issues", text="问题")

        tree.column("target", width=80, anchor="center")
        tree.column("actual", width=80, anchor="center")
        tree.column("revision", width=60, anchor="center")
        tree.column("consistency", width=60, anchor="center")
        tree.column("memory", width=60, anchor="center")
        tree.column("issues", width=200)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        issue_labels = {
            "missing_chapter_plan": "缺少章节计划",
            "missing_chapter": "缺少章节正文",
            "chapter_too_short": "章节字数不足",
            "missing_consistency": "缺少一致性检查",
            "missing_memory": "缺少记忆整理",
        }

        for ch in chapters:
            vi = ch.get("volume_index", "?")
            ci = ch.get("chapter_index", "?")
            item_id = tree.insert("", "end", text=f"第{vi}卷第{ci}章", values=(
                ch.get("target_words", 0),
                ch.get("actual_words", 0),
                "✓" if ch.get("has_revision") else "✗",
                "✓" if ch.get("has_consistency") else "✗",
                "✓" if ch.get("has_memory") else "✗",
                ", ".join(issue_labels.get(i, i) for i in ch.get("issues", [])),
            ))
            if ch.get("blocking"):
                tree.item(item_id, tags=("blocking",))

        tree.tag_configure("blocking", foreground=COLORS["danger"])
