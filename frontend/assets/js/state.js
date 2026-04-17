const STORAGE_KEY = 'novel-agent-clean:selected-project-id';
const STEP_STORAGE_PREFIX = 'novel-agent-clean:selected-step:';

export function getSelectedProjectId() {
  return localStorage.getItem(STORAGE_KEY) || new URLSearchParams(window.location.search).get('project_id') || '';
}

export function setSelectedProjectId(projectId) {
  const url = new URL(window.location.href);
  if (projectId) {
    localStorage.setItem(STORAGE_KEY, projectId);
    url.searchParams.set('project_id', projectId);
  } else {
    localStorage.removeItem(STORAGE_KEY);
    url.searchParams.delete('project_id');
  }
  window.history.replaceState({}, '', url);
}

export function syncProjectId(projectId) {
  setSelectedProjectId(projectId);
}

export function getPageProjectId() {
  return getSelectedProjectId();
}

export function listFromText(value) {
  return String(value ?? '')
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function textFromList(items) {
  return Array.isArray(items) ? items.join('\n') : '';
}

export function setPreferredStep(pageKey, step) {
  if (step) {
    sessionStorage.setItem(`${STEP_STORAGE_PREFIX}${pageKey}`, step);
  }
}

export function getPreferredStep(pageKey) {
  return sessionStorage.getItem(`${STEP_STORAGE_PREFIX}${pageKey}`) || '';
}

export function withProjectQuery(path, projectId) {
  if (!projectId) {
    return path;
  }
  const url = new URL(path, window.location.origin);
  url.searchParams.set('project_id', projectId);
  return `${url.pathname}${url.search}`;
}

export function syncTopNavLinks(projectId = getSelectedProjectId()) {
  document.querySelectorAll('.nav-links a').forEach((link) => {
    const currentPath = new URL(link.getAttribute('href') || '/', window.location.origin).pathname;
    if (currentPath === '/') {
      link.href = '/';
      return;
    }
    link.href = withProjectQuery(currentPath, projectId);
  });
}
