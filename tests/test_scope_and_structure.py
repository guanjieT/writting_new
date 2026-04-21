from __future__ import annotations

import json
import unittest

from novel_agent.agents import BaseAgent
from novel_agent.domain import Artifact, ArtifactSummary, NovelProject, ProjectInput, WorkflowOrderError, WorkflowStep
from novel_agent.orchestrator import NovelOrchestrator
from novel_agent.services import AuditService, ProjectService, _artifact_key, _project_step_from_artifacts, build_artifact


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

if __name__ == "__main__":
    unittest.main()
