"""Shared tkinter theme utilities for the desktop GUI.

The GUI intentionally stays on the stdlib tkinter/ttk stack so the app keeps its
zero-extra-GUI-dependency footprint.  The styling below borrows common patterns
from modern writing/dashboard apps: a calm ink sidebar, card-based content,
large readable typography, stronger spacing, and soft focus states.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#f3f6fb",
    "bg_alt": "#eef2f7",
    "panel": "#ffffff",
    "panel_alt": "#f7f9fc",
    "card": "#ffffff",
    "card_hover": "#f9fbff",
    "sidebar": "#0f172a",
    "sidebar_alt": "#111c33",
    "sidebar_card": "#18243a",
    "sidebar_border": "#263752",
    "text": "#111827",
    "muted": "#64748b",
    "subtle": "#94a3b8",
    "border": "#dbe3ef",
    "border_strong": "#cbd5e1",
    "accent": "#4f46e5",
    "accent_hover": "#4338ca",
    "accent_soft": "#eef2ff",
    "accent_line": "#c7d2fe",
    "success": "#059669",
    "success_soft": "#ecfdf5",
    "warning": "#d97706",
    "warning_soft": "#fffbeb",
    "danger": "#dc2626",
    "danger_soft": "#fef2f2",
    "info": "#0284c7",
    "info_soft": "#e0f2fe",
    "input_bg": "#ffffff",
    "input_border": "#cbd5e1",
}

FONTS = {
    "base": ("TkDefaultFont", 10),
    "small": ("TkDefaultFont", 9),
    "tiny": ("TkDefaultFont", 8),
    "title": ("TkDefaultFont", 18, "bold"),
    "hero": ("TkDefaultFont", 22, "bold"),
    "section": ("TkDefaultFont", 12, "bold"),
    "stat": ("TkDefaultFont", 24, "bold"),
    "mono": ("TkFixedFont", 10),
}


def apply_theme(root: tk.Tk) -> None:
    """Apply the app-wide visual theme to ttk and root widgets."""
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=COLORS["bg"])

    style.configure(".", font=FONTS["base"], foreground=COLORS["text"])

    # Layout surfaces
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("AppShell.TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Surface.TFrame", background=COLORS["panel"], relief="flat")
    style.configure("Card.TFrame", background=COLORS["card"], relief="solid", borderwidth=1, bordercolor=COLORS["border"])
    style.configure("Hero.TFrame", background=COLORS["accent_soft"], relief="solid", borderwidth=1, bordercolor=COLORS["accent_line"])
    style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
    style.configure("SidebarCard.TFrame", background=COLORS["sidebar_card"], relief="solid", borderwidth=1, bordercolor=COLORS["sidebar_border"])
    style.configure("Status.TFrame", background=COLORS["panel"], relief="solid", borderwidth=1, bordercolor=COLORS["border"])

    # Labels
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"])
    style.configure("Hero.TLabel", background=COLORS["accent_soft"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
    style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
    style.configure("CardMuted.TLabel", background=COLORS["card"], foreground=COLORS["muted"])
    style.configure("HeroMuted.TLabel", background=COLORS["accent_soft"], foreground=COLORS["muted"])
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["title"])
    style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["title"])
    style.configure("HeroTitle.TLabel", background=COLORS["accent_soft"], foreground=COLORS["text"], font=FONTS["hero"])
    style.configure("Section.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("PanelSection.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("StatValue.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=FONTS["stat"])
    style.configure("StatLabel.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=FONTS["small"])

    style.configure("SidebarTitle.TLabel", background=COLORS["sidebar"], foreground="#ffffff", font=("TkDefaultFont", 16, "bold"))
    style.configure("SidebarMuted.TLabel", background=COLORS["sidebar"], foreground="#b9c6d8")
    style.configure("SidebarSection.TLabel", background=COLORS["sidebar"], foreground="#e2e8f0", font=("TkDefaultFont", 10, "bold"))
    style.configure("SidebarCard.TLabel", background=COLORS["sidebar_card"], foreground="#ffffff")
    style.configure("SidebarCardMuted.TLabel", background=COLORS["sidebar_card"], foreground="#b9c6d8")
    style.configure("SidebarValue.TLabel", background=COLORS["sidebar_card"], foreground="#ffffff")

    # Label frames
    style.configure("TLabelframe", background=COLORS["bg"], bordercolor=COLORS["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("Panel.TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid", borderwidth=1)
    style.configure("Panel.TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("Sidebar.TLabelframe", background=COLORS["sidebar"], bordercolor=COLORS["sidebar_border"], relief="solid", borderwidth=1)
    style.configure("Sidebar.TLabelframe.Label", background=COLORS["sidebar"], foreground="#d9e3f5", font=("TkDefaultFont", 10, "bold"))

    # Buttons
    style.configure("TButton", padding=(12, 7), background=COLORS["panel_alt"], foreground=COLORS["text"], bordercolor=COLORS["border_strong"], focusthickness=1, focuscolor=COLORS["accent_line"])
    style.map("TButton", background=[("active", "#eef2f7"), ("pressed", "#e2e8f0"), ("disabled", "#f1f5f9")], foreground=[("disabled", COLORS["subtle"])])
    style.configure("Accent.TButton", foreground="#ffffff", background=COLORS["accent"], bordercolor=COLORS["accent"], font=("TkDefaultFont", 10, "bold"))
    style.map("Accent.TButton", background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"]), ("disabled", "#a5b4fc")])
    style.configure("Danger.TButton", foreground="#ffffff", background=COLORS["danger"], bordercolor=COLORS["danger"], font=("TkDefaultFont", 10, "bold"))
    style.map("Danger.TButton", background=[("active", "#b91c1c"), ("pressed", "#991b1b"), ("disabled", "#fecaca")])
    style.configure("Ghost.TButton", padding=(10, 6), background=COLORS["panel"], bordercolor=COLORS["border"], foreground=COLORS["text"])
    style.map("Ghost.TButton", background=[("active", COLORS["panel_alt"])])

    style.configure("Nav.TButton", anchor="w", padding=(14, 10), foreground="#cbd5e1", background=COLORS["sidebar"], bordercolor=COLORS["sidebar"], font=("TkDefaultFont", 10, "bold"))
    style.map("Nav.TButton", background=[("active", COLORS["sidebar_card"]), ("pressed", COLORS["sidebar_card"])], foreground=[("active", "#ffffff")])
    style.configure("NavSelected.TButton", anchor="w", padding=(14, 10), foreground="#ffffff", background=COLORS["accent"], bordercolor=COLORS["accent"], font=("TkDefaultFont", 10, "bold"))
    style.map("NavSelected.TButton", background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"])])
    style.configure("Step.TButton", anchor="w", padding=(10, 7), background=COLORS["panel"], bordercolor=COLORS["border"], foreground=COLORS["text"])
    style.map("Step.TButton", background=[("active", COLORS["accent_soft"]), ("pressed", COLORS["accent_soft"])])
    style.configure("StepSelected.TButton", anchor="w", padding=(10, 7), background=COLORS["accent_soft"], bordercolor=COLORS["accent_line"], foreground=COLORS["accent"], font=("TkDefaultFont", 10, "bold"))

    # Inputs and data widgets
    style.configure("TEntry", fieldbackground=COLORS["input_bg"], bordercolor=COLORS["input_border"], lightcolor=COLORS["input_border"], darkcolor=COLORS["input_border"], padding=7)
    style.map("TEntry", bordercolor=[("focus", COLORS["accent"]), ("invalid", COLORS["danger"])])
    style.configure("TSpinbox", fieldbackground=COLORS["input_bg"], bordercolor=COLORS["input_border"], padding=7)
    style.configure("TCombobox", fieldbackground=COLORS["input_bg"], background=COLORS["input_bg"], bordercolor=COLORS["input_border"], padding=6)
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0, tabmargins=(2, 4, 2, 0))
    style.configure("TNotebook.Tab", padding=(14, 9), background=COLORS["panel_alt"], foreground=COLORS["muted"], bordercolor=COLORS["border"])
    style.map("TNotebook.Tab", background=[("selected", COLORS["panel"])], foreground=[("selected", COLORS["accent"])])
    style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=32, bordercolor=COLORS["border"], borderwidth=0)
    style.configure("Treeview.Heading", background=COLORS["panel_alt"], foreground=COLORS["text"], font=("TkDefaultFont", 10, "bold"), padding=8)
    style.map("Treeview", background=[("selected", COLORS["accent_soft"])], foreground=[("selected", COLORS["text"])])
    style.configure("Horizontal.TProgressbar", troughcolor=COLORS["bg_alt"], background=COLORS["accent"], bordercolor=COLORS["border"], lightcolor=COLORS["accent"], darkcolor=COLORS["accent"])
    style.configure("Vertical.TScrollbar", background=COLORS["panel_alt"], troughcolor=COLORS["bg_alt"], bordercolor=COLORS["border"], arrowcolor=COLORS["muted"])

    # Native Tk menu colors where supported.
    root.option_add("*Menu.background", COLORS["panel"])
    root.option_add("*Menu.foreground", COLORS["text"])
    root.option_add("*Menu.activeBackground", COLORS["accent_soft"])
    root.option_add("*Menu.activeForeground", COLORS["accent"])


def style_text_widget(widget: tk.Text, *, height: int | None = None, readonly: bool = False) -> None:
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
        padx=10,
        pady=8,
        wrap="word",
        font=FONTS["base"],
        spacing1=2,
        spacing3=4,
    )
    if readonly:
        widget.configure(bg=COLORS["panel_alt"])
    if height is not None:
        widget.configure(height=height)


def style_listbox(widget: tk.Listbox) -> None:
    """Apply the app list style to project and navigation listboxes."""
    widget.configure(
        bg=COLORS["panel"],
        fg=COLORS["text"],
        selectbackground=COLORS["accent_soft"],
        selectforeground=COLORS["accent"],
        activestyle="none",
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=("TkDefaultFont", 11),
        borderwidth=0,
        selectborderwidth=0,
    )


def make_card(parent: tk.Widget, *, padding: tuple[int, int] = (14, 12)) -> ttk.Frame:
    """Create a consistently padded card frame."""
    outer = ttk.Frame(parent, style="Card.TFrame")
    inner = ttk.Frame(outer, style="Card.TFrame")
    inner.pack(fill="both", expand=True, padx=padding[0], pady=padding[1])
    # Store a convenient reference for callers that want the inner content area.
    outer.content = inner  # type: ignore[attr-defined]
    return outer
