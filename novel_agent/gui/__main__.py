"""GUI entry point.

Usage: python -m novel_agent.gui
"""

from __future__ import annotations


def main() -> None:
    from .app_modern import main as run_modern_gui

    run_modern_gui()


if __name__ == "__main__":
    main()
