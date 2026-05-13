"""Entry point for novel-agent-clean.

GUI mode:  python -m novel_agent.gui
"""

from __future__ import annotations


def main() -> None:
    import tkinter as tk

    from .gui.app import App

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
