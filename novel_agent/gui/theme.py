"""Shared tkinter theme utilities for the desktop GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "panel_alt": "#eef3f8",
    "sidebar": "#17202f",
    "sidebar_alt": "#213044",
    "text": "#1d2733",
    "muted": "#667085",
    "border": "#d8dee8",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_soft": "#dbeafe",
    "success": "#15803d",
    "warning": "#b45309",
    "danger": "#b42318",
    "info": "#0369a1",
    "input_bg": "#ffffff",
    "input_border": "#cbd5e1",
}

FONTS = {
    "base": ("TkDefaultFont", 10),
    "small": ("TkDefaultFont", 9),
    "title": ("TkDefaultFont", 16, "bold"),
    "section": ("TkDefaultFont", 12, "bold"),
    "stat": ("TkDefaultFont", 20, "bold"),
}


def apply_theme(root: tk.Tk) -> None:
    """Apply the app-wide visual theme to ttk and root widgets."""
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=COLORS["bg"])

    style.configure(".", font=FONTS["base"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Card.TFrame", background=COLORS["panel"], relief="solid", borderwidth=1)
    style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
    style.configure("Status.TFrame", background=COLORS["panel"])

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
    style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["title"])
    style.configure("Section.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("SidebarTitle.TLabel", background=COLORS["sidebar"], foreground="#ffffff", font=("TkDefaultFont", 13, "bold"))
    style.configure("SidebarMuted.TLabel", background=COLORS["sidebar"], foreground="#b8c2d4")
    style.configure("SidebarValue.TLabel", background=COLORS["sidebar_alt"], foreground="#ffffff")

    style.configure("TLabelframe", background=COLORS["bg"], bordercolor=COLORS["border"], relief="solid")
    style.configure("TLabelframe.Label", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("Panel.TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
    style.configure("Panel.TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("Sidebar.TLabelframe", background=COLORS["sidebar"], bordercolor=COLORS["sidebar_alt"], relief="solid")
    style.configure("Sidebar.TLabelframe.Label", background=COLORS["sidebar"], foreground="#d9e3f5", font=("TkDefaultFont", 10, "bold"))

    style.configure("TButton", padding=(10, 6), background=COLORS["panel_alt"], bordercolor=COLORS["border"])
    style.map("TButton", background=[("active", "#e2e8f0"), ("disabled", "#eef2f7")])
    style.configure("Accent.TButton", foreground="#ffffff", background=COLORS["accent"], bordercolor=COLORS["accent"])
    style.map("Accent.TButton", background=[("active", COLORS["accent_hover"]), ("disabled", "#93b4f5")])
    style.configure("Danger.TButton", foreground="#ffffff", background=COLORS["danger"], bordercolor=COLORS["danger"])
    style.map("Danger.TButton", background=[("active", "#991b1b"), ("disabled", "#efb0aa")])
    style.configure("Nav.TButton", anchor="w", padding=(12, 8), foreground="#d9e3f5", background=COLORS["sidebar"], bordercolor=COLORS["sidebar"])
    style.map("Nav.TButton", background=[("active", COLORS["sidebar_alt"])])
    style.configure("NavSelected.TButton", anchor="w", padding=(12, 8), foreground="#ffffff", background=COLORS["accent"], bordercolor=COLORS["accent"])
    style.map("NavSelected.TButton", background=[("active", COLORS["accent_hover"])])

    style.configure("TEntry", fieldbackground=COLORS["input_bg"], bordercolor=COLORS["input_border"], padding=5)
    style.configure("TSpinbox", fieldbackground=COLORS["input_bg"], bordercolor=COLORS["input_border"], padding=5)
    style.configure("TCombobox", fieldbackground=COLORS["input_bg"], bordercolor=COLORS["input_border"], padding=4)
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(12, 7), background=COLORS["panel_alt"])
    style.map("TNotebook.Tab", background=[("selected", COLORS["panel"])], foreground=[("selected", COLORS["accent"])])
    style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=28, bordercolor=COLORS["border"])
    style.configure("Treeview.Heading", background=COLORS["panel_alt"], foreground=COLORS["text"], font=("TkDefaultFont", 10, "bold"))
    style.map("Treeview", background=[("selected", COLORS["accent_soft"])], foreground=[("selected", COLORS["text"])])
    style.configure("Horizontal.TProgressbar", troughcolor=COLORS["panel_alt"], background=COLORS["accent"], bordercolor=COLORS["border"])


def style_text_widget(widget: tk.Text, *, height: int | None = None) -> None:
    """Apply consistent spacing and colors to a Text widget."""
    widget.configure(
        bg=COLORS["input_bg"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["input_border"],
        highlightcolor=COLORS["accent"],
        padx=8,
        pady=6,
        wrap="word",
        font=FONTS["base"],
    )
    if height is not None:
        widget.configure(height=height)


def style_listbox(widget: tk.Listbox) -> None:
    """Apply the app list style to project and navigation listboxes."""
    widget.configure(
        bg=COLORS["panel"],
        fg=COLORS["text"],
        selectbackground=COLORS["accent_soft"],
        selectforeground=COLORS["text"],
        activestyle="none",
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        font=FONTS["base"],
    )
