"""SQLite storage backend for long-form projects and tasks.

The current default repository still uses JSON files to preserve compatibility.
This module provides a local SQLite implementation that can be adopted by
configuration in a later migration.  It stores the full Pydantic document for
compatibility and also keeps indexed metadata columns for future partial queries.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .domain import NovelProject, ProjectRepository, TaskRecord, TaskStore, TaskStatus, utc_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    document_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    project_id TEXT NOT NULL,
    artifact_key TEXT NOT NULL,
    step TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    volume_index INTEGER,
    chapter_index INTEGER,
    state TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY(project_id, artifact_key)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    volume_index INTEGER,
    chapter_index INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    document_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_project_step ON artifacts(project_id, step, scope_kind, volume_index, chapter_index);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
"""


class SQLiteProjectRepository(ProjectRepository):
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def list(self) -> list[NovelProject]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT document_json FROM projects ORDER BY updated_at DESC").fetchall()
            return [NovelProject.model_validate_json(row["document_json"]) for row in rows]

    def get(self, project_id: str) -> NovelProject | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT document_json FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if row is None:
                return None
            return NovelProject.model_validate_json(row["document_json"])

    def save(self, project: NovelProject) -> NovelProject:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(project_id, title, genre, status, updated_at, document_json)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    title = excluded.title,
                    genre = excluded.genre,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    document_json = excluded.document_json
                """,
                (
                    project.project_id,
                    project.input.title,
                    project.input.genre,
                    project.status.value,
                    project.updated_at.isoformat(),
                    project.model_dump_json(),
                ),
            )
            conn.execute("DELETE FROM artifacts WHERE project_id = ?", (project.project_id,))
            for artifact in project.artifacts.values():
                metadata = artifact.metadata or {}
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        project_id, artifact_key, step, scope_kind, volume_index, chapter_index,
                        state, title, content, summary_json, metadata_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project.project_id,
                        artifact.key,
                        str(metadata.get("step") or ""),
                        str(metadata.get("scope_kind") or "project"),
                        metadata.get("volume_index"),
                        metadata.get("chapter_index"),
                        str(metadata.get("state") or "active"),
                        artifact.title,
                        artifact.content,
                        artifact.summary.model_dump_json(),
                        artifact.model_dump_json(),
                    ),
                )
            return project

    def delete(self, project_id: str) -> NovelProject | None:
        with self._lock, self._connect() as conn:
            project = self.get(project_id)
            if project is None:
                return None
            conn.execute("DELETE FROM artifacts WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            return project


class SQLiteTaskStore(TaskStore):
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self._mark_interrupted_tasks()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _write(self, conn: sqlite3.Connection, task: TaskRecord) -> TaskRecord:
        conn.execute(
            """
            INSERT INTO tasks(task_id, project_id, task_name, scope_kind, volume_index, chapter_index, status, created_at, document_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                project_id = excluded.project_id,
                task_name = excluded.task_name,
                scope_kind = excluded.scope_kind,
                volume_index = excluded.volume_index,
                chapter_index = excluded.chapter_index,
                status = excluded.status,
                created_at = excluded.created_at,
                document_json = excluded.document_json
            """,
            (
                task.task_id,
                task.project_id,
                task.task_name,
                task.scope_kind,
                task.volume_index,
                task.chapter_index,
                task.status.value if hasattr(task.status, "value") else str(task.status),
                task.created_at.isoformat(),
                task.model_dump_json(),
            ),
        )
        return task

    def _mark_interrupted_tasks(self) -> None:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT document_json FROM tasks WHERE status IN ('pending', 'running')").fetchall()
            for row in rows:
                task = TaskRecord.model_validate_json(row["document_json"])
                task.status = TaskStatus.FAILED
                task.error = task.error or "task interrupted by service restart"
                task.finished_at = task.finished_at or utc_now()
                self._write(conn, task)

    def create(self, task: TaskRecord) -> TaskRecord:
        with self._lock, self._connect() as conn:
            return self._write(conn, task).model_copy(deep=True)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT document_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return TaskRecord.model_validate_json(row["document_json"]).model_copy(deep=True)

    def list(self, project_id: str | None = None) -> list[TaskRecord]:
        with self._lock, self._connect() as conn:
            if project_id is None:
                rows = conn.execute("SELECT document_json FROM tasks ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute("SELECT document_json FROM tasks WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
            return [TaskRecord.model_validate_json(row["document_json"]).model_copy(deep=True) for row in rows]

    def update(self, task: TaskRecord) -> TaskRecord:
        with self._lock, self._connect() as conn:
            return self._write(conn, task).model_copy(deep=True)

    def delete(self, task_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))

    def delete_by_project(self, project_id: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            return int(cur.rowcount or 0)
