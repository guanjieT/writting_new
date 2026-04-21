import { getStepDependencies } from './step-meta.js';
import {
  dependencySelectionFor,
  getStepScopeKind,
  hasExplicitScopeSelection,
  normalizeScopeSelection,
  selectionForStep,
  taskMatchesStepSelection,
} from './scope-utils.js';

export function getArtifactsForStep(snapshot, step) {
  const artifacts = Object.values(snapshot?.artifacts || {});
  return artifacts.filter((artifact) => artifact?.metadata?.step === step || artifact?.key === step);
}

export function getArtifact(snapshot, step) {
  const artifacts = getArtifactsForStep(snapshot, step);
  return artifacts.length ? artifacts[artifacts.length - 1] : null;
}

export function getScopedArtifact(snapshot, step, selection = {}) {
  const scopeKind = getStepScopeKind(step);
  const normalized = normalizeScopeSelection(selection);
  return getArtifactsForStep(snapshot, step).find((artifact) => {
    const metadata = artifact?.metadata || {};
    if ((metadata.scope_kind || 'project') !== scopeKind) {
      return false;
    }
    if (scopeKind === 'volume') {
      return Number(metadata.volume_index || 0) === normalized.volumeIndex;
    }
    if (scopeKind === 'chapter') {
      return Number(metadata.volume_index || 0) === normalized.volumeIndex && Number(metadata.chapter_index || 0) === normalized.chapterIndex;
    }
    return true;
  }) || null;
}

export function getArtifactForStep(snapshot, step, selection = {}) {
  if (hasExplicitScopeSelection(selection)) {
    return getScopedArtifact(snapshot, step, selection);
  }
  return getArtifact(snapshot, step);
}

function dependencyArtifactFor(step, dependency, snapshot, selection = {}) {
  return getScopedArtifact(snapshot, dependency, dependencySelectionFor(step, dependency, selection));
}

export function isUnlocked(step, snapshot, dependencyMap, selection = {}) {
  return getStepDependencies(step, dependencyMap).every((item) => Boolean(dependencyArtifactFor(step, item, snapshot, selection)));
}

export function getTasksForStepSelection(step, tasks = [], selection = {}) {
  const stepSelection = selectionForStep(step, selection);
  return tasks.filter((task) => task.task_name === step && taskMatchesStepSelection(task, step, stepSelection));
}

export function getTasksForSelection(tasks = [], steps = [], selection = {}) {
  const stepKeys = new Set(steps.map((step) => (typeof step === 'string' ? step : step?.key)).filter(Boolean));
  return tasks.filter((task) => {
    const step = task.task_name;
    if (stepKeys.size && !stepKeys.has(step)) {
      return false;
    }
    return taskMatchesStepSelection(task, step, selectionForStep(step, selection));
  });
}

export function findLatestTaskForStep(step, tasks = [], selection = {}) {
  return getTasksForStepSelection(step, tasks, selection)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
}

export function getStepStatus(step, snapshot, dependencyMap, tasks = [], selection = {}) {
  const artifact = getArtifactForStep(snapshot, step, selection);
  if (artifact) {
    return artifact?.metadata?.stale ? { tone: 'warn', text: '已失效' } : { tone: 'success', text: '已产出' };
  }

  const latestTask = findLatestTaskForStep(step, tasks, selection);
  if (latestTask?.status === 'failed') {
    return { tone: 'danger', text: '执行失败' };
  }
  if (latestTask?.status === 'pending' || latestTask?.status === 'running') {
    return { tone: 'accent', text: '执行中' };
  }
  if (isUnlocked(step, snapshot, dependencyMap, selection)) {
    return { tone: 'warn', text: '待处理' };
  }
  return { tone: 'soft', text: '未解锁' };
}
