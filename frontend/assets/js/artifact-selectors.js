import { getArtifactForStep, getScopedArtifact } from './app-config.js';
import { getStepDependencies, getStepScopeKind } from './step-meta.js';
import { dependencySelectionFor, normalizeScopeSelection, taskMatchesStepSelection } from './scope-utils.js';

function dependencyArtifactFor(step, dependency, snapshot, selection = {}) {
  return getScopedArtifact(snapshot, dependency, dependencySelectionFor(step, dependency, selection));
}

function findLatestTaskForStep(step, tasks = [], selection = {}) {
  const matchedTasks = tasks.filter((task) => task.task_name === step && taskMatchesStepSelection(task, step, selection));
  return matchedTasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
}

export function completedSteps(snapshot) {
  return new Set(Object.values(snapshot?.artifacts || {}).map((artifact) => artifact?.metadata?.step || artifact?.key).filter(Boolean));
}

export function isUnlocked(step, snapshot, dependencyMap, selection = {}) {
  return getStepDependencies(step, dependencyMap).every((item) => Boolean(dependencyArtifactFor(step, item, snapshot, selection)));
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

export {
  getArtifactForStep,
  getScopedArtifact,
  getStepScopeKind,
  findLatestTaskForStep,
  normalizeScopeSelection,
};

export { getArtifact, getArtifactsForStep } from './app-config.js';
