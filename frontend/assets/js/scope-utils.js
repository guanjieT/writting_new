const STEP_SCOPE_KIND = {
  outline: 'project',
  rough_volume_outline: 'project',
  volume_outline: 'volume',
  rough_chapter_plan: 'volume',
  chapter_plan: 'chapter',
  chapter: 'chapter',
  revision: 'chapter',
  consistency: 'chapter',
  memory: 'chapter',
};

function parsePositiveInt(value, fallback = 1) {
  const parsed = Number(value || fallback);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback;
}

function parsePositiveIntOrNull(value) {
  if (value === undefined || value === null || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : null;
}

export function getStepScopeKind(step) {
  return STEP_SCOPE_KIND[step] || 'project';
}

export function normalizeScopeSelection(selection = {}, payload = {}) {
  return {
    volumeIndex: parsePositiveInt(selection.volumeIndex ?? selection.volume_index ?? payload.volumeIndex ?? payload.volume_index, 1),
    chapterIndex: parsePositiveInt(selection.chapterIndex ?? selection.chapter_index ?? payload.chapterIndex ?? payload.chapter_index, 1),
  };
}

export function hasExplicitScopeSelection(selection = {}, payload = {}) {
  return Boolean(
    selection
    && (
      selection.volumeIndex !== undefined
      || selection.volume_index !== undefined
      || selection.chapterIndex !== undefined
      || selection.chapter_index !== undefined
      || payload.volumeIndex !== undefined
      || payload.volume_index !== undefined
      || payload.chapterIndex !== undefined
      || payload.chapter_index !== undefined
    )
  );
}

export function readScopeSelectionFromUrl(search = window.location.search) {
  const params = new URLSearchParams(search);
  return normalizeScopeSelection({
    volumeIndex: params.get('volume_index') || 1,
    chapterIndex: params.get('chapter_index') || 1,
  });
}

export function syncScopeSelectionToUrl(selection) {
  const url = new URL(window.location.href);
  url.searchParams.set('volume_index', String(selection.volumeIndex || 1));
  url.searchParams.set('chapter_index', String(selection.chapterIndex || 1));
  window.history.replaceState({}, '', url);
}

function getProjectVolumeCount(snapshot) {
  return Math.max(Number(snapshot?.project?.input?.target_volume_count || 1), 1);
}

function getProjectChapterCount(snapshot) {
  return Math.max(Number(snapshot?.project?.input?.target_chapters_per_volume || 1), 1);
}

function getDefaultChapterCount(snapshot) {
  return getProjectChapterCount(snapshot);
}

export function clampScopeSelection(snapshot, selection = {}, { getChapterCountForVolume } = {}) {
  const normalized = normalizeScopeSelection(selection);
  const volumeIndex = Math.min(normalized.volumeIndex, getProjectVolumeCount(snapshot));
  const chapterResolver = getChapterCountForVolume || getDefaultChapterCount;
  const chapterCount = Math.max(Number(chapterResolver(snapshot, volumeIndex)) || 1, 1);
  const chapterIndex = Math.min(normalized.chapterIndex, chapterCount);
  return {
    volumeIndex,
    chapterIndex,
  };
}

export function selectionForStep(step, selection = {}) {
  const scopeKind = getStepScopeKind(step);
  if (scopeKind === 'project') {
    return {};
  }

  const normalized = normalizeScopeSelection(selection);
  if (scopeKind === 'volume') {
    return { volumeIndex: normalized.volumeIndex };
  }
  if (scopeKind === 'chapter') {
    return { volumeIndex: normalized.volumeIndex, chapterIndex: normalized.chapterIndex };
  }
  return {};
}

export function dependencySelectionFor(step, dependency, selection = {}) {
  if (!hasExplicitScopeSelection(selection)) {
    return {};
  }

  const normalized = normalizeScopeSelection(selection);
  const dependencyScope = getStepScopeKind(dependency);
  if (dependencyScope === 'volume') {
    return { volumeIndex: normalized.volumeIndex };
  }
  if (dependencyScope === 'chapter') {
    return { volumeIndex: normalized.volumeIndex, chapterIndex: normalized.chapterIndex };
  }
  return {};
}

export function normalizeTaskScope(task = {}) {
  const metadata = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const scopeKind = String(task.scope_kind || metadata.scope_kind || 'project');
  return {
    scopeKind,
    volumeIndex: parsePositiveIntOrNull(task.volume_index ?? metadata.volume_index),
    chapterIndex: parsePositiveIntOrNull(task.chapter_index ?? metadata.chapter_index),
  };
}

export function taskMatchesStepSelection(task, step, selection = {}) {
  const scopeKind = getStepScopeKind(step);
  const taskScope = normalizeTaskScope(task);
  if (scopeKind === 'project') {
    return taskScope.scopeKind === 'project';
  }

  const normalized = normalizeScopeSelection(selection);
  if (scopeKind === 'volume') {
    return taskScope.scopeKind === 'volume' && taskScope.volumeIndex === normalized.volumeIndex;
  }
  if (scopeKind === 'chapter') {
    return taskScope.scopeKind === 'chapter' && taskScope.volumeIndex === normalized.volumeIndex && taskScope.chapterIndex === normalized.chapterIndex;
  }
  return false;
}
