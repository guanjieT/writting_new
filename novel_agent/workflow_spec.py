from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkflowStepSpec:
    key: str
    label: str
    depends_on: tuple[str, ...] = ()
    page: str = "workflow"
    scope: str = "project"


WORKFLOW_STEPS: tuple[WorkflowStepSpec, ...] = (
    WorkflowStepSpec("requirements", "需求分析"),
    WorkflowStepSpec("story_bible", "世界观设定", ("requirements",)),
    WorkflowStepSpec("characters", "角色框架", ("requirements", "story_bible")),
    WorkflowStepSpec("outline", "总纲", ("requirements", "story_bible", "characters"), page="outline"),
    WorkflowStepSpec("rough_volume_outline", "粗卷纲", ("outline",), page="outline"),
    WorkflowStepSpec("volume_outline", "完善卷纲", ("rough_volume_outline",), page="volume-outline", scope="volume"),
    WorkflowStepSpec("rough_chapter_plan", "粗章纲", ("volume_outline",), page="volume-outline", scope="volume"),
    WorkflowStepSpec("chapter_plan", "完善章节计划", ("rough_chapter_plan",), page="chapter-plan", scope="chapter"),
    WorkflowStepSpec("chapter", "章节生成", ("chapter_plan",)),
    WorkflowStepSpec("revision", "修订", ("chapter",)),
    WorkflowStepSpec("consistency", "一致性检查", ("chapter",)),
    WorkflowStepSpec("memory", "记忆整理", ("chapter",)),
)


def workflow_dependency_map() -> dict[str, list[str]]:
    return {step.key: list(step.depends_on) for step in WORKFLOW_STEPS}


def workflow_dependent_map() -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for step in WORKFLOW_STEPS:
        children.setdefault(step.key, [])
    for step in WORKFLOW_STEPS:
        for dependency in step.depends_on:
            children.setdefault(dependency, []).append(step.key)
    return {key: value for key, value in children.items()}


def workflow_label_map() -> dict[str, str]:
    return {step.key: step.label for step in WORKFLOW_STEPS}


def workflow_spec() -> dict[str, object]:
    return {
        "steps": [asdict(step) for step in WORKFLOW_STEPS],
        "dependencies": workflow_dependency_map(),
    }