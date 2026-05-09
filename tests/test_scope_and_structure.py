from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from novel_agent.agents import BaseAgent, ChapterAgent
from novel_agent.context_builder import build_generation_context
from novel_agent.domain import AgentContext, Artifact, ArtifactSummary, NovelProject, ProjectInput, TaskRecord, TaskStatus, WorkflowOrderError, WorkflowStep
from novel_agent.infrastructure import FileProjectRepository, FilePromptStore, FileTaskStore, MemoryTaskStore
from novel_agent.orchestrator import NovelOrchestrator
from novel_agent.quality import build_quality_report
from novel_agent.services import AuditService, ProjectService, PromptService, TaskService, _artifact_key, _project_step_from_artifacts, build_artifact, build_project_manuscript, build_project_progress


class MemoryProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[str, NovelProject] = {}

    def list(self) -> list[NovelProject]:
        return [project.model_copy(deep=True) for project in self._projects.values()]

    def get(self, project_id: str) -> NovelProject | None:
        project = self._projects.get(project_id)
        return None if project is None else project.model_copy(deep=True)

    def save(self, project: NovelProject) -> NovelProject:
        stored = project.model_copy(deep=True)
        self._projects[stored.project_id] = stored
        return stored.model_copy(deep=True)

    def delete(self, project_id: str) -> NovelProject | None:
        project = self._projects.pop(project_id, None)
        return None if project is None else project.model_copy(deep=True)


class ScopeAndStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MemoryProjectRepository()
        self.project_service = ProjectService(self.repo)
        self.project = self.project_service.create(ProjectInput(title="测试项目", genre="奇幻", target_volume_count=2, target_chapters_per_volume=4))
        self.orchestrator = NovelOrchestrator(
            project_service=self.project_service,
            audit_service=AuditService(),
            agent_dependencies=object(),
            agents={},
        )

    def test_chapter_artifact_keys_are_scoped(self) -> None:
        first = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "章节正文",
            "第一章内容",
            summary=ArtifactSummary(),
            step="chapter",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=1,
        )
        second = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 2}),
            "章节正文",
            "第二章内容",
            summary=ArtifactSummary(),
            step="chapter",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=2,
        )

        project, _ = self.project_service.register_generated_artifact(self.project.project_id, first)
        project, _ = self.project_service.register_generated_artifact(self.project.project_id, second)

        self.assertIn(first.key, project.artifacts)
        self.assertIn(second.key, project.artifacts)
        self.assertNotEqual(first.key, second.key)

    def test_volume_and_chapter_checks_use_structured_payloads(self) -> None:
        rough_volume_outline = build_artifact(
            "rough_volume_outline",
            "粗卷纲",
            "第2卷看起来存在，但不应被内容正则误判",
            summary=ArtifactSummary(structured={
                "volumes": [
                    {"volume_index": 1, "title": "第一卷", "summary": "s", "goal": "g", "main_conflict": "c", "ending_hook": "h", "target_chapter_count": 4, "target_words": 10000},
                    {"volume_index": 2, "title": "第二卷", "summary": "s2", "goal": "g2", "main_conflict": "c2", "ending_hook": "h2", "target_chapter_count": 4, "target_words": 10000},
                ]
            }),
            step="rough_volume_outline",
            scope_kind="project",
        )
        rough_chapter_plan = build_artifact(
            _artifact_key("rough_chapter_plan", {"scope_kind": "volume", "volume_index": 2}),
            "粗章纲",
            "第3章看起来存在，但不应被内容正则误判",
            summary=ArtifactSummary(structured={
                "volume_index": 2,
                "total_target_chapters": 2,
                "chapters": [
                    {"chapter_index": 1, "title": "一", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                    {"chapter_index": 2, "title": "二", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                ],
            }),
            step="rough_chapter_plan",
            scope_kind="volume",
            volume_index=2,
        )
        self.project_service.register_generated_artifact(self.project.project_id, rough_volume_outline)
        self.project_service.register_generated_artifact(self.project.project_id, rough_chapter_plan)

        self.orchestrator._ensure_step_ready(self.project_service.get(self.project.project_id), "volume_outline", {"volume_index": 2})
        self.orchestrator._ensure_step_ready(self.project_service.get(self.project.project_id), "chapter_plan", {"volume_index": 2, "chapter_index": 2})

        bad_volume = build_artifact(
            "rough_volume_outline",
            "粗卷纲",
            "第2卷在文本里出现，但 structured 没有它",
            summary=ArtifactSummary(structured={
                "volumes": [
                    {"volume_index": 1, "title": "第一卷", "summary": "s", "goal": "g", "main_conflict": "c", "ending_hook": "h", "target_chapter_count": 4, "target_words": 10000},
                ]
            }),
            step="rough_volume_outline",
            scope_kind="project",
        )
        bad_project = self.project_service.create(ProjectInput(title="坏项目", genre="奇幻"))
        self.project_service.register_generated_artifact(bad_project.project_id, bad_volume)
        with self.assertRaises(WorkflowOrderError):
            self.orchestrator._ensure_step_ready(self.project_service.get(bad_project.project_id), "volume_outline", {"volume_index": 2})

        bad_chapter = build_artifact(
            _artifact_key("rough_chapter_plan", {"scope_kind": "volume", "volume_index": 1}),
            "粗章纲",
            "第3章在文本里出现，但 structured 没有它",
            summary=ArtifactSummary(structured={
                "volume_index": 1,
                "total_target_chapters": 2,
                "chapters": [
                    {"chapter_index": 1, "title": "一", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                    {"chapter_index": 2, "title": "二", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                ],
            }),
            step="rough_chapter_plan",
            scope_kind="volume",
            volume_index=1,
        )
        bad_project = self.project_service.create(ProjectInput(title="坏章节项目", genre="奇幻", target_volume_count=1, target_chapters_per_volume=2))
        self.project_service.register_generated_artifact(bad_project.project_id, bad_chapter)
        with self.assertRaises(WorkflowOrderError):
            self.orchestrator._ensure_step_ready(self.project_service.get(bad_project.project_id), "chapter_plan", {"volume_index": 1, "chapter_index": 3})

    def test_remove_artifact_deletes_only_scoped_chain(self) -> None:
        chapter = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 3}),
            "章节正文",
            "目标章节",
            summary=ArtifactSummary(),
            step="chapter",
            scope_kind="chapter",
            volume_index=2,
            chapter_index=3,
        )
        revision = build_artifact(
            _artifact_key("revision", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 3}),
            "修订",
            "修订结果",
            summary=ArtifactSummary(),
            step="revision",
            scope_kind="chapter",
            volume_index=2,
            chapter_index=3,
        )
        consistency = build_artifact(
            _artifact_key("consistency", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 3}),
            "一致性检查",
            "检查结果",
            summary=ArtifactSummary(),
            step="consistency",
            scope_kind="chapter",
            volume_index=2,
            chapter_index=3,
        )
        memory = build_artifact(
            _artifact_key("memory", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 3}),
            "记忆整理",
            "记忆摘要",
            summary=ArtifactSummary(),
            step="memory",
            scope_kind="chapter",
            volume_index=2,
            chapter_index=3,
        )
        other_chapter = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 4}),
            "章节正文",
            "其他章节",
            summary=ArtifactSummary(),
            step="chapter",
            scope_kind="chapter",
            volume_index=2,
            chapter_index=4,
        )

        for artifact in (chapter, revision, consistency, memory, other_chapter):
            self.project_service.register_generated_artifact(self.project.project_id, artifact)

        project, removed = self.project_service.remove_artifact(self.project.project_id, chapter.key)

        self.assertEqual(set(removed), {chapter.key, revision.key, consistency.key, memory.key})
        self.assertIn(other_chapter.key, project.artifacts)
        self.assertNotIn(chapter.key, project.artifacts)
        self.assertNotIn(revision.key, project.artifacts)
        self.assertNotIn(consistency.key, project.artifacts)
        self.assertNotIn(memory.key, project.artifacts)

    def test_two_volumes_two_chapters_keep_scopes_isolated_and_reconstruct_status(self) -> None:
        artifacts = [
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "章节正文",
                "第一卷第一章",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("revision", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "修订",
                "第一卷第一章修订",
                summary=ArtifactSummary(),
                step="revision",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 2}),
                "章节正文",
                "第一卷第二章",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=2,
            ),
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
                "章节正文",
                "第二卷第一章",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=2,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("consistency", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
                "一致性检查",
                "第二卷第一章一致性",
                summary=ArtifactSummary(),
                step="consistency",
                scope_kind="chapter",
                volume_index=2,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("memory", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
                "记忆整理",
                "第二卷第一章记忆",
                summary=ArtifactSummary(),
                step="memory",
                scope_kind="chapter",
                volume_index=2,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 2}),
                "章节正文",
                "第二卷第二章",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=2,
                chapter_index=2,
            ),
        ]

        for artifact in artifacts:
            self.project_service.register_generated_artifact(self.project.project_id, artifact)

        project = self.project_service.get(self.project.project_id)
        self.assertEqual(len(project.artifacts), 7)
        self.assertEqual(_project_step_from_artifacts(project.artifacts), WorkflowStep.MEMORY)
        self.assertIn(_artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}), project.artifacts)
        self.assertIn(_artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 2}), project.artifacts)

        project, removed = self.project_service.remove_artifact(
            self.project.project_id,
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
        )

        self.assertEqual(set(removed), {
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
            _artifact_key("consistency", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
            _artifact_key("memory", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 1}),
        })
        self.assertIn(_artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}), project.artifacts)
        self.assertIn(_artifact_key("revision", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}), project.artifacts)
        self.assertIn(_artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 2, "chapter_index": 2}), project.artifacts)
        self.assertEqual(_project_step_from_artifacts(project.artifacts), WorkflowStep.REVISION)

    def test_project_step_recovery_uses_scoped_key_prefix_when_metadata_missing(self) -> None:
        project = self.project_service.create(ProjectInput(title="键回推项目", genre="奇幻"))
        project.artifacts = {
            "chapter:1:1": Artifact(key="chapter:1:1", title="章节正文", content="正文", metadata={"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "revision:1:1": Artifact(key="revision:1:1", title="修订", content="修订", metadata={"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "memory:1:1": Artifact(key="memory:1:1", title="记忆整理", content="记忆", metadata={"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
        }

        self.assertEqual(_project_step_from_artifacts(project.artifacts), WorkflowStep.MEMORY)

    def test_project_step_recovery_ignores_stale_artifacts(self) -> None:
        project = self.project_service.create(ProjectInput(title="失效回推项目", genre="奇幻"))
        project.artifacts = {
            "chapter:1:1": Artifact(key="chapter:1:1", title="章节正文", content="正文", metadata={"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "memory:1:1": Artifact(key="memory:1:1", title="记忆整理", content="记忆", metadata={"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1, "stale": True, "state": "stale"}),
        }

        self.assertEqual(_project_step_from_artifacts(project.artifacts), WorkflowStep.CHAPTER)

    def test_stale_dependency_blocks_downstream_step(self) -> None:
        chapter_plan = build_artifact(
            _artifact_key("chapter_plan", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "章节计划",
            "旧计划",
            summary=ArtifactSummary(),
            step="chapter_plan",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=1,
            stale=True,
            state="stale",
        )
        self.project_service.register_generated_artifact(self.project.project_id, chapter_plan)

        with self.assertRaises(WorkflowOrderError):
            self.orchestrator._ensure_step_ready(self.project_service.get(self.project.project_id), "chapter", {"volume_index": 1, "chapter_index": 1})

    def test_update_project_clears_artifacts_and_old_tasks(self) -> None:
        task_store = MemoryTaskStore()
        task_service = TaskService(task_store, ThreadPoolExecutor(max_workers=1))
        task_store.create(TaskRecord(project_id=self.project.project_id, task_name="requirements"))
        self.orchestrator.task_service = task_service
        self.project_service.register_generated_artifact(
            self.project.project_id,
            build_artifact("requirements", "需求", "旧需求", summary=ArtifactSummary(), step="requirements", scope_kind="project"),
        )

        updated = self.orchestrator.update_project(
            self.project.project_id,
            ProjectInput(title="新设定", genre="科幻", target_volume_count=1, target_chapters_per_volume=2),
        )

        self.assertEqual(updated.current_step, WorkflowStep.CREATED)
        self.assertEqual(updated.artifacts, {})
        self.assertEqual(updated.artifact_history, {})
        self.assertEqual(updated.knowledge_base, [])
        self.assertEqual(task_service.list(self.project.project_id), [])

    def test_replacing_artifact_archives_previous_version(self) -> None:
        first = build_artifact(
            "requirements",
            "需求",
            "旧需求",
            summary=ArtifactSummary(key_facts=["旧事实"]),
            step="requirements",
            scope_kind="project",
        )
        second = build_artifact(
            "requirements",
            "需求",
            "新需求",
            summary=ArtifactSummary(key_facts=["新事实"]),
            step="requirements",
            scope_kind="project",
        )

        self.project_service.register_generated_artifact(self.project.project_id, first)
        project, _ = self.project_service.register_generated_artifact(self.project.project_id, second)

        self.assertEqual(project.artifacts["requirements"].content, "新需求")
        self.assertEqual(len(project.artifact_history["requirements"]), 1)
        self.assertEqual(project.artifact_history["requirements"][0].content, "旧需求")
        self.assertTrue(project.artifacts["requirements"].metadata.get("version_id"))
        self.assertTrue(project.artifacts["requirements"].metadata.get("previous_version_id"))

    def test_generated_artifact_updates_knowledge_base(self) -> None:
        artifact = build_artifact(
            "requirements",
            "需求",
            "需求正文",
            summary=ArtifactSummary(
                key_facts=["事实 A"],
                constraints=["约束 B"],
                open_questions=["问题 C"],
            ),
            step="requirements",
            scope_kind="project",
        )

        project, _ = self.project_service.register_generated_artifact(self.project.project_id, artifact)
        kinds = {(item.kind, item.text) for item in project.knowledge_base}

        self.assertIn(("fact", "事实 A"), kinds)
        self.assertIn(("constraint", "约束 B"), kinds)
        self.assertIn(("open_question", "问题 C"), kinds)

    def test_project_progress_counts_chapter_completion(self) -> None:
        self.project_service.register_generated_artifact(
            self.project.project_id,
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "章节正文",
                "正文",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
        )

        progress = build_project_progress(self.project_service.get(self.project.project_id))

        self.assertEqual(progress["planned_chapters"], 8)
        self.assertEqual(progress["completed_chapters"], 1)
        self.assertEqual(progress["volumes"][0]["chapters"][0]["chapter"], True)

    def test_project_manuscript_export_prefers_revision_over_draft(self) -> None:
        artifacts = [
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "章节正文",
                "草稿正文",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
            build_artifact(
                _artifact_key("revision", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "修订",
                "修订正文",
                summary=ArtifactSummary(),
                step="revision",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
        ]
        for artifact in artifacts:
            self.project_service.register_generated_artifact(self.project.project_id, artifact)

        manuscript = build_project_manuscript(self.project_service.get(self.project.project_id))

        self.assertIn("# 测试项目", manuscript)
        self.assertIn("## 第1卷", manuscript)
        self.assertIn("### 第1章", manuscript)
        self.assertIn("修订正文", manuscript)
        self.assertNotIn("草稿正文", manuscript)

    def test_quality_report_flags_missing_review_steps(self) -> None:
        self.project_service.register_generated_artifact(
            self.project.project_id,
            build_artifact(
                _artifact_key("chapter_plan", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "章节计划",
                "计划",
                summary=ArtifactSummary(structured={"min_words": 10}),
                step="chapter_plan",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
        )
        self.project_service.register_generated_artifact(
            self.project.project_id,
            build_artifact(
                _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
                "章节正文",
                "短",
                summary=ArtifactSummary(),
                step="chapter",
                scope_kind="chapter",
                volume_index=1,
                chapter_index=1,
            ),
        )

        report = build_quality_report(self.project_service.get(self.project.project_id))

        self.assertFalse(report["ready_for_export"])
        self.assertIn("chapter_too_short", report["chapters"][0]["issues"])
        self.assertIn("missing_consistency", report["chapters"][0]["issues"])
        self.assertIn("missing_memory", report["chapters"][0]["issues"])

    def test_later_chapter_context_includes_previous_chapter_artifacts_and_knowledge(self) -> None:
        first_chapter = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "第一章",
            "第一章正文",
            summary=ArtifactSummary(key_facts=["主角拿到铜钥匙"]),
            step="chapter",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=1,
        )
        second_chapter = build_artifact(
            _artifact_key("chapter", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 2}),
            "第二章",
            "第二章正文",
            summary=ArtifactSummary(key_facts=["主角打开密室"]),
            step="chapter",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=2,
        )
        for artifact in (first_chapter, second_chapter):
            self.project_service.register_generated_artifact(self.project.project_id, artifact)

        project = self.project_service.get(self.project.project_id)
        context = build_generation_context(project, "chapter", {"volume_index": 1, "chapter_index": 3})

        recent_titles = [item["title"] for item in context["recent_chapter_artifacts"]]
        knowledge_texts = [item["text"] for item in context["knowledge_base"]]
        self.assertIn("第一章", recent_titles)
        self.assertIn("第二章", recent_titles)
        self.assertIn("主角拿到铜钥匙", knowledge_texts)
        self.assertIn("主角打开密室", knowledge_texts)

    def test_file_task_store_persists_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first_store = FileTaskStore(Path(temp_dir))
            task = first_store.create(TaskRecord(project_id=self.project.project_id, task_name="requirements", input_payload={"foo": "bar"}))
            task.status = TaskStatus.COMPLETED
            task.result = {"ok": True}
            first_store.update(task)

            second_store = FileTaskStore(Path(temp_dir))
            restored = second_store.get(task.task_id)

            self.assertIsNotNone(restored)
            self.assertEqual(restored.task_id, task.task_id)
            self.assertEqual(restored.result, {"ok": True})
            self.assertEqual(restored.input_payload, {"foo": "bar"})

    def test_file_task_store_marks_unfinished_tasks_interrupted_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first_store = FileTaskStore(Path(temp_dir))
            task = first_store.create(TaskRecord(project_id=self.project.project_id, task_name="requirements"))
            task.status = TaskStatus.RUNNING
            first_store.update(task)

            second_store = FileTaskStore(Path(temp_dir))
            restored = second_store.get(task.task_id)

            self.assertIsNotNone(restored)
            self.assertEqual(restored.status.value, "failed")
            self.assertIn("interrupted", restored.error or "")

    def test_file_prompt_store_validates_required_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "requirements.md").write_text("ok", encoding="utf-8")
            prompt_store = FilePromptStore(prompt_dir)

            prompt_store.validate_required(["requirements"])
            with self.assertRaises(FileNotFoundError):
                prompt_store.validate_required(["requirements", "chapter"])

    def test_prompt_render_replaces_named_variables_without_breaking_json_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "template.md").write_text(
                '示例 JSON：{"title": "占位"}\n项目：{project_summary}',
                encoding="utf-8",
            )
            rendered = PromptService(FilePromptStore(prompt_dir)).render("template", {"project_summary": "项目 A"})

            self.assertIn('{"title": "占位"}', rendered)
            self.assertIn("项目：项目 A", rendered)

    def test_file_project_repository_uses_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FileProjectRepository(Path(temp_dir))
            project = NovelProject(input=ProjectInput(title="文件项目", genre="奇幻"))
            repository.save(project)

            restored = repository.get(project.project_id)

            self.assertIsNotNone(restored)
            self.assertEqual(restored.input.title, "文件项目")

    def test_rough_chapter_plan_generation_infers_missing_chapter_indices(self) -> None:
        agent = BaseAgent("rough_chapter_plan", WorkflowStep.ROUGH_CHAPTER_PLAN, "rough_chapter_plan", "rough_chapter_plan", "粗章纲")
        payload = {
            "content": "第1卷章节骨架摘要。",
            "overview": "第1卷章节骨架。",
            "key_facts": [],
            "constraints": [],
            "open_questions": [],
            "best_for_reason": "",
            "structured": {
                "volume_index": 1,
                "total_target_chapters": 2,
                "chapters": [
                    {"title": "一", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                    {"title": "二", "summary": "s", "chapter_type": "t", "pov_character": "p", "main_event": "e", "conflict": "c", "hook": "h", "target_words": 1000},
                ],
            },
        }

        generated = agent._parse_generated_payload(json.dumps(payload, ensure_ascii=False))

        self.assertEqual([chapter["chapter_index"] for chapter in generated.structured["chapters"]], [1, 2])

    def test_chapter_agent_uses_current_chapter_plan_as_parent(self) -> None:
        first_plan = build_artifact(
            _artifact_key("chapter_plan", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 1}),
            "第一章计划",
            "第一章计划正文",
            summary=ArtifactSummary(structured={
                "volume_index": 1,
                "chapter_index": 1,
                "summary": "第一章目标",
                "main_event": "第一章事件",
                "scene_summaries": ["第一章场景"],
            }),
            step="chapter_plan",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=1,
        )
        second_plan = build_artifact(
            _artifact_key("chapter_plan", {"scope_kind": "chapter", "volume_index": 1, "chapter_index": 2}),
            "第二章计划",
            "第二章计划正文",
            summary=ArtifactSummary(structured={
                "volume_index": 1,
                "chapter_index": 2,
                "summary": "第二章目标",
                "main_event": "第二章事件",
                "scene_summaries": ["第二章场景"],
            }),
            step="chapter_plan",
            scope_kind="chapter",
            volume_index=1,
            chapter_index=2,
        )

        for artifact in (first_plan, second_plan):
            self.project_service.register_generated_artifact(self.project.project_id, artifact)

        project = self.project_service.get(self.project.project_id)
        agent = ChapterAgent()
        variables = agent.build_variables(project, AgentContext(project_id=project.project_id, payload={"volume_index": 1, "chapter_index": 2}))
        parent = json.loads(variables["parent_artifact_json"])
        selected_artifacts = json.loads(variables["artifacts_json"])
        prompt = FilePromptStore(Path("/tmp/nonexistent-prompts")).load("chapter").format(**variables)

        self.assertEqual(parent["key"], second_plan.key)
        self.assertEqual(selected_artifacts["chapter_plan"]["key"], second_plan.key)
        self.assertIn("当前章节计划", prompt)
        self.assertIn("第二章计划", prompt)
        self.assertNotIn("第一章计划", prompt)

        first_variables = agent.build_variables(project, AgentContext(project_id=project.project_id, payload={"volume_index": 1, "chapter_index": 1}))
        self.assertEqual(json.loads(first_variables["parent_artifact_json"])["key"], first_plan.key)

if __name__ == "__main__":
    unittest.main()
