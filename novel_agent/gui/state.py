"""Shared application state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScopeSelection:
    volume_index: int = 1
    chapter_index: int = 1


@dataclass
class AppShared:
    """Mutable state bag passed to every view."""

    container: Any = None  # AppContainer
    task_monitor: Any = None  # TaskMonitor

    current_project_id: str = ""
    current_snapshot: dict | None = None
    current_tasks: list = field(default_factory=list)
    current_step: str = ""
    scope: ScopeSelection = field(default_factory=ScopeSelection)

    def project(self) -> Any | None:
        if self.current_snapshot:
            return self.current_snapshot.get("project")
        return None

    def project_input(self) -> Any | None:
        project = self.project()
        if project:
            return project.get("input")
        return None

    def artifacts(self) -> dict:
        if self.current_snapshot:
            return self.current_snapshot.get("artifacts", {})
        return {}
