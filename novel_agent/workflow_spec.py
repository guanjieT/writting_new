from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkflowStepSpec:
    key: str
    label: str
    depends_on: tuple[str, ...] = ()


WORKFLOW_STEPS: tuple[WorkflowStepSpec, ...] = (
    WorkflowStepSpec("requirements", "需求分析"),
    WorkflowStepSpec("story_bible", "世界观设定", ("requirements",)),
    WorkflowStepSpec("characters", "角色框架", ("requirements", "story_bible")),
    WorkflowStepSpec("outline", "总纲生成", ("requirements", "story_bible", "characters")),
    WorkflowStepSpec("volume_outline", "卷纲生成", ("outline",)),
    WorkflowStepSpec("chapter_plan", "章节计划", ("volume_outline",)),
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