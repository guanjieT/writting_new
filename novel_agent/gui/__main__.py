"""GUI entry point.

Usage: python -m novel_agent.gui
"""

from __future__ import annotations

import tkinter as tk


def main() -> None:
    from .app import App

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
