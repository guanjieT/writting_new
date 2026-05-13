"""Artifact viewer — read-only display of generated artifact content."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..theme import COLORS, style_text_widget


def render_artifact_viewer(parent: tk.Widget, artifact: dict | None, step_label: str = "") -> ttk.Frame:
    """Build a scrollable frame showing artifact details.

    Returns the frame widget. Caller should pack/grid it.
    """
    frame = ttk.Frame(parent)

    if not artifact:
        empty = ttk.Label(frame, text="暂无产物，请先生成此步骤", style="Muted.TLabel")
        empty.pack(padx=12, pady=24)
        return frame

    # Title bar
    title_frame = ttk.Frame(frame)
    title_frame.pack(fill="x", padx=8, pady=(8, 0))

    title = artifact.get("title") or step_label or "产物"
    meta = artifact.get("metadata", {}) or {}
    stale = meta.get("stale") or meta.get("state") == "stale"

    ttk.Label(title_frame, text=title, style="Section.TLabel").pack(side="left")
    if stale:
        ttk.Label(title_frame, text="已失效", foreground=COLORS["warning"], font=("TkDefaultFont", 9)).pack(side="left", padx=8)

    # Notebook for sections
    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    # Content tab
    content_frame = ttk.Frame(nb)
    nb.add(content_frame, text="内容")

    content_text = tk.Text(content_frame, wrap="word", state="normal")
    style_text_widget(content_text)
    content_scroll = ttk.Scrollbar(content_frame, orient="vertical", command=content_text.yview)
    content_text.configure(yscrollcommand=content_scroll.set)

    content = str(artifact.get("content", "") or "")
    if not content:
        gen = meta.get("generated_payload", {}) or {}
        content = str(gen.get("content", "") or "")
    content_text.insert("1.0", content or "（无内容）")
    content_text.configure(state="disabled")

    content_text.pack(side="left", fill="both", expand=True)
    content_scroll.pack(side="right", fill="y")

    # Summary tab
    summary = artifact.get("summary", {}) or {}
    if summary:
        summary_frame = ttk.Frame(nb)
        nb.add(summary_frame, text="摘要")

        summary_text = tk.Text(summary_frame, wrap="word", state="normal")
        style_text_widget(summary_text)
        sum_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=summary_text.yview)
        summary_text.configure(yscrollcommand=sum_scroll.set)

        lines = []
        overview = str(summary.get("overview") or "").strip()
        if overview:
            lines.append(f"[概述]\n{overview}\n")

        key_facts = summary.get("key_facts") or []
        if key_facts:
            lines.append("[关键事实]")
            for f in key_facts:
                lines.append(f"  • {f}")
            lines.append("")

        constraints = summary.get("constraints") or []
        if constraints:
            lines.append("[约束条件]")
            for c in constraints:
                lines.append(f"  • {c}")
            lines.append("")

        open_qs = summary.get("open_questions") or []
        if open_qs:
            lines.append("[未决问题]")
            for q in open_qs:
                lines.append(f"  • {q}")

        summary_text.insert("1.0", "\n".join(lines) if lines else "（无摘要）")
        summary_text.configure(state="disabled")

        summary_text.pack(side="left", fill="both", expand=True)
        sum_scroll.pack(side="right", fill="y")

    # Structured data tab (if available)
    structured = _get_structured(artifact)
    if structured:
        struct_frame = ttk.Frame(nb)
        nb.add(struct_frame, text="结构化数据")

        tree = ttk.Treeview(struct_frame, columns=("value",), show="tree")
        tree_scroll = ttk.Scrollbar(struct_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)

        tree.heading("#0", text="字段")
        tree.heading("value", text="值")
        tree.column("value", width=400)

        _populate_tree(tree, "", structured)

        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    # Metadata tab
    meta_frame = ttk.Frame(nb)
    nb.add(meta_frame, text="元数据")

    meta_text = tk.Text(meta_frame, wrap="word", state="normal")
    style_text_widget(meta_text)
    meta_scroll = ttk.Scrollbar(meta_frame, orient="vertical", command=meta_text.yview)
    meta_text.configure(yscrollcommand=meta_scroll.set)

    import json
    clean_meta = {k: v for k, v in meta.items() if k != "generated_payload"}
    meta_text.insert("1.0", json.dumps(clean_meta, ensure_ascii=False, indent=2, default=str))
    meta_text.configure(state="disabled")

    meta_text.pack(side="left", fill="both", expand=True)
    meta_scroll.pack(side="right", fill="y")

    # Key info line
    info_frame = ttk.Frame(frame)
    info_frame.pack(fill="x", padx=8, pady=(0, 8))
    scope_kind = meta.get("scope_kind", "project")
    vi = meta.get("volume_index", "")
    ci = meta.get("chapter_index", "")
    scope_text = "全书"
    if scope_kind == "volume":
        scope_text = f"第{vi}卷"
    elif scope_kind == "chapter":
        scope_text = f"第{vi}卷第{ci}章"
    ttk.Label(info_frame, text=f"范围: {scope_text}  | 键: {artifact.get('key', '')}", style="Muted.TLabel").pack(side="left")

    return frame


def _get_structured(artifact: dict) -> dict | None:
    meta = artifact.get("metadata", {}) or {}
    gen = meta.get("generated_payload", {}) or {}
    if isinstance(gen.get("structured"), dict) and gen["structured"]:
        return gen["structured"]
    summary = artifact.get("summary", {}) or {}
    if isinstance(summary.get("structured"), dict) and summary["structured"]:
        return summary["structured"]
    return None


def _populate_tree(tree: ttk.Treeview, parent: str, data: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                child = tree.insert(parent, "end", text=str(key), values=("",))
                _populate_tree(tree, child, value)
            else:
                tree.insert(parent, "end", text=str(key), values=(str(value)[:200],))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                child = tree.insert(parent, "end", text=f"[{i}]", values=("",))
                _populate_tree(tree, child, item)
            else:
                tree.insert(parent, "end", text=f"[{i}]", values=(str(item)[:200],))
    else:
        tree.insert(parent, "end", text="", values=(str(data)[:200],))
