"""TaskMonitor — tkinter.after() polling for async task completion."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Any, Callable

from novel_agent.domain import TaskStatus


@dataclass
class _PollEntry:
    on_complete: Callable[[dict], None]
    on_error: Callable[[dict | None], None]
    on_progress: Callable[[dict], None] | None = None


@dataclass
class TaskMonitor:
    """Polls task_service.get(task_id) on the tkinter event loop via root.after()."""

    root: tk.Tk
    task_service: Any
    _polling: dict[str, _PollEntry] = field(default_factory=dict)
    _interval_ms: int = 1200

    def start(
        self,
        task_id: str,
        on_complete: Callable[[dict], None],
        on_error: Callable[[dict | None], None],
        on_progress: Callable[[dict], None] | None = None,
    ) -> None:
        self._polling[task_id] = _PollEntry(on_complete, on_error, on_progress)
        self._schedule(task_id)

    def cancel(self, task_id: str) -> None:
        self._polling.pop(task_id, None)
        try:
            self.task_service.cancel(task_id)
        except Exception:
            pass

    def _schedule(self, task_id: str) -> None:
        self.root.after(self._interval_ms, self._poll, task_id)

    def _poll(self, task_id: str) -> None:
        entry = self._polling.get(task_id)
        if entry is None:
            return

        try:
            task = self.task_service.get(task_id)
        except Exception:
            task = None

        if task is None:
            self._polling.pop(task_id, None)
            entry.on_error(None)
            return

        status = task.status if hasattr(task, "status") else task.get("status", "")
        status_str = str(status)

        if status_str in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
            self._polling.pop(task_id, None)
            raw = task.model_dump(mode="json") if hasattr(task, "model_dump") else task
            if status_str == TaskStatus.COMPLETED.value:
                entry.on_complete(raw)
            else:
                entry.on_error(raw)
        else:
            if entry.on_progress:
                raw = task.model_dump(mode="json") if hasattr(task, "model_dump") else task
                entry.on_progress(raw)
            self._schedule(task_id)

    @property
    def active_count(self) -> int:
        return len(self._polling)
