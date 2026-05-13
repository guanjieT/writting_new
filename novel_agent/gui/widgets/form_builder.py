"""Dynamic form builder — maps FieldDef to tkinter widgets."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ..step_fields import (
    FIELD_CHECKBOX,
    FIELD_LIST,
    FIELD_NUMBER,
    FIELD_SELECT,
    FIELD_TEXTAREA,
    get_step_def,
)
from ..scope_utils import (
    get_field_display_value,
    get_field_select_options,
    normalize_scope_selection,
)
from ..theme import COLORS, style_text_widget


def _list_to_text(items: Any) -> str:
    if isinstance(items, list):
        return "\n".join(str(x) for x in items)
    return str(items or "")


def _text_to_list(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def build_form(
    parent: tk.Widget,
    step_key: str,
    snapshot: dict | None = None,
    selection: dict | None = None,
    on_ai_complete: Callable[[str, dict], None] | None = None,
) -> tuple[ttk.Frame, Callable[[], dict]]:
    """Build a scrollable form for a workflow step.

    Returns (form_frame, read_payload) where read_payload() returns a dict
    of all field values suitable for passing to orchestrator.dispatch().
    """
    step_def = get_step_def(step_key)

    # Outer container
    outer = ttk.Frame(parent)

    # Scrollable canvas for the form
    canvas = tk.Canvas(outer, highlightthickness=0, bg=COLORS["bg"])
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    form_frame = ttk.Frame(canvas)

    form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=form_frame, anchor="nw", tags="form_frame")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Make form_frame width track canvas width
    def _on_canvas_configure(event: tk.Event) -> None:
        canvas.itemconfig("form_frame", width=event.width)
    canvas.bind("<Configure>", _on_canvas_configure)

    # Mouse wheel scrolling
    def _on_mousewheel(event: tk.Event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    outer.grid_rowconfigure(0, weight=1)
    outer.grid_columnconfigure(0, weight=1)

    # Step description
    if step_def.description:
        desc = ttk.Label(form_frame, text=step_def.description, wraplength=620, style="Muted.TLabel")
        desc.grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 10))

    # Collect widgets for reading values later
    _widgets: dict[str, dict] = {}  # field_key -> {widget, var, field_type, list}
    _row = 1

    # Split into primary and advanced fields
    fields = step_def.fields
    primary_fields = [f for f in fields if not f.advanced]
    advanced_fields = [f for f in fields if f.advanced]

    # Render primary fields
    for field in primary_fields:
        _row = _render_field_row(form_frame, field, _row, _widgets, step_key, snapshot, selection, on_ai_complete)

    # Advanced fields in a collapsible frame
    if advanced_fields:
        _row += 1
        adv_frame = ttk.LabelFrame(form_frame, text="高级设置", padding=10)
        adv_frame.grid(row=_row, column=0, columnspan=4, sticky="ew", padx=8, pady=8)

        # Start collapsed — just place fields inside
        adv_inner = ttk.Frame(adv_frame)
        adv_inner.grid(row=0, column=0, sticky="ew")
        adv_row = 0
        for field in advanced_fields:
            adv_row = _render_field_row(adv_inner, field, adv_row, _widgets, step_key, snapshot, selection, None)
        _row += 1

    # Scope hidden fields
    norm = normalize_scope_selection(selection)
    if get_step_def(step_key).key not in ("requirements", "story_bible", "characters", "outline", "rough_volume_outline"):
        _widgets["volume_index"] = {"widget": None, "var": tk.StringVar(value=str(norm["volume_index"])), "field_type": "hidden"}
    chapter_scope_steps = ("chapter_plan", "chapter", "revision", "consistency", "memory")
    if step_key in chapter_scope_steps:
        _widgets["chapter_index"] = {"widget": None, "var": tk.StringVar(value=str(norm["chapter_index"])), "field_type": "hidden"}

    def read_payload() -> dict:
        """Read all form values into a dict suitable for orchestrator.dispatch()."""
        payload: dict = {}
        for key, wdata in _widgets.items():
            ftype = wdata["field_type"]
            if ftype == "hidden":
                val = wdata["var"].get()
                try:
                    payload[key] = int(val)
                except (ValueError, TypeError):
                    payload[key] = val
            elif ftype == FIELD_CHECKBOX:
                payload[key] = wdata["var"].get() == "1"
            elif ftype == FIELD_SELECT:
                raw = wdata["var"].get()
                payload[key] = wdata.get("_value_map", {}).get(raw, raw)
            elif ftype == FIELD_LIST:
                payload[key] = _text_to_list(wdata["var"].get())
            elif ftype == FIELD_NUMBER:
                val = wdata["var"].get()
                try:
                    payload[key] = int(val)
                except (ValueError, TypeError):
                    try:
                        payload[key] = float(val)
                    except (ValueError, TypeError):
                        payload[key] = val
            else:
                payload[key] = wdata["var"].get()
        return payload

    return outer, read_payload


def _render_field_row(
    parent: ttk.Frame,
    field: Any,  # FieldDef
    row: int,
    widgets: dict,
    step_key: str,
    snapshot: dict | None,
    selection: dict | None,
    on_ai_complete: Callable | None,
) -> int:
    """Render a single field row. Returns next row index."""
    key = field.key
    label = field.label
    ftype = field.field_type

    # Enhance field with step_key for default value resolution
    field.step_key = step_key

    # Label
    lbl = ttk.Label(parent, text=label)
    lbl.grid(row=row, column=0, sticky="nw", padx=(8, 12), pady=6)

    # Determine default value
    default_val = get_field_display_value(field, snapshot, selection)

    if ftype == FIELD_CHECKBOX:
        var = tk.StringVar(value="1" if default_val else "0")
        cb = ttk.Checkbutton(parent, variable=var, onvalue="1", offvalue="0")
        cb.grid(row=row, column=1, sticky="w", padx=4, pady=6)
        widgets[key] = {"widget": cb, "var": var, "field_type": ftype}

    elif ftype == FIELD_SELECT:
        options = get_field_select_options(field, snapshot, selection)
        var = tk.StringVar(value=str(default_val or ""))
        if options:
            values = [o["label"] for o in options]
            value_map = {o["label"]: o["value"] for o in options}
            combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
            # Set current selection by value
            for o in options:
                if o["value"] == str(default_val):
                    var.set(o["label"])
                    break
            combo.grid(row=row, column=1, sticky="ew", padx=4, pady=6)

            def _make_reader(vm: dict, v: tk.StringVar) -> Callable:
                def _read() -> str:
                    return vm.get(v.get(), v.get())
                return _read

            widgets[key] = {
                "widget": combo,
                "var": var,
                "field_type": ftype,
                "_value_map": value_map,
            }
        else:
            # No options available — show a label
            empty = ttk.Label(parent, text=field.empty_label or "暂无可选项", style="Muted.TLabel")
            empty.grid(row=row, column=1, sticky="w", padx=4, pady=6)
            widgets[key] = {"widget": empty, "var": tk.StringVar(value=""), "field_type": ftype}

    elif ftype == FIELD_TEXTAREA:
        text_widget = tk.Text(parent, height=field.rows or 4, width=50, wrap="word")
        style_text_widget(text_widget)
        text_val = _list_to_text(default_val) if field.is_list else str(default_val or "")
        text_widget.insert("1.0", text_val)

        text_scroll = ttk.Scrollbar(parent, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scroll.set)

        text_widget.grid(row=row, column=1, sticky="ew", padx=4, pady=6)
        text_scroll.grid(row=row, column=2, sticky="ns", pady=6)

        # Use a StringVar proxy
        var = tk.StringVar(value=text_val)

        def _on_text_change(*args: Any) -> None:
            var.set(text_widget.get("1.0", "end-1c"))
        text_widget.bind("<KeyRelease>", _on_text_change)

        widgets[key] = {"widget": text_widget, "var": var, "field_type": ftype, "list": field.is_list}

    elif ftype == FIELD_NUMBER:
        var = tk.StringVar(value=str(default_val or 0))
        spin = ttk.Spinbox(parent, textvariable=var, from_=0, to=999999, increment=field.step_ or 1)
        spin.grid(row=row, column=1, sticky="ew", padx=4, pady=6)
        widgets[key] = {"widget": spin, "var": var, "field_type": ftype}

    else:  # text (single line)
        var = tk.StringVar(value=str(default_val or ""))
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=6)
        if field.placeholder:
            entry.insert(0, "")
        widgets[key] = {"widget": entry, "var": var, "field_type": ftype}

    # AI complete button for eligible fields
    if (
        on_ai_complete
        and ftype not in (FIELD_SELECT, FIELD_CHECKBOX)
        and not field.advanced
        and not field.disabled
    ):
        ai_btn = ttk.Button(
            parent,
            text="AI",
            width=3,
            command=lambda f=field: _handle_ai_complete(f, step_key, widgets, snapshot, selection, on_ai_complete),
        )
        ai_btn.grid(row=row, column=2 if ftype != FIELD_TEXTAREA else 3, padx=(2, 8), pady=6)

    # Configure column weights
    parent.grid_columnconfigure(1, weight=1)

    return row + 1


def _handle_ai_complete(
    field: Any,
    step_key: str,
    widgets: dict,
    snapshot: dict | None,
    selection: dict | None,
    callback: Callable,
) -> None:
    """Collect current form context and invoke AI completion callback."""
    # Build context payload from current form values
    payload: dict = {}
    for key, wdata in widgets.items():
        ftype = wdata.get("field_type", "")
        if ftype == FIELD_CHECKBOX:
            payload[key] = wdata["var"].get() == "1"
        elif ftype in (FIELD_LIST, FIELD_TEXTAREA):
            val = wdata["var"].get()
            payload[key] = _text_to_list(val) if wdata.get("list") else val
        elif ftype == FIELD_NUMBER:
            try:
                payload[key] = int(wdata["var"].get())
            except (ValueError, TypeError):
                payload[key] = wdata["var"].get()
        else:
            payload[key] = wdata["var"].get()

    callback(field.key, payload)


def set_field_value(widgets: dict, key: str, value: Any) -> None:
    """Programmatically set a form field value."""
    if key not in widgets:
        return
    wdata = widgets[key]
    ftype = wdata["field_type"]
    widget = wdata["widget"]
    var = wdata["var"]

    if ftype == FIELD_CHECKBOX:
        var.set("1" if value else "0")
    elif ftype == FIELD_LIST:
        var.set(_list_to_text(value))
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", _list_to_text(value))
    elif ftype == FIELD_TEXTAREA:
        var.set(str(value or ""))
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", str(value or ""))
    elif ftype == FIELD_SELECT:
        vm = wdata.get("_value_map", {})
        reverse_map = {str(v): k for k, v in vm.items()}
        var.set(reverse_map.get(str(value), str(value)))
    elif ftype == FIELD_NUMBER:
        var.set(str(value or 0))
    else:
        var.set(str(value or ""))
