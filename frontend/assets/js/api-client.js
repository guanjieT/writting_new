const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
};

async function readError(response) {
  try {
    const payload = await response.json();
    return payload.detail || payload.message || JSON.stringify(payload);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

export async function requestJson(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    headers: body ? DEFAULT_HEADERS : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  if (response.status === 204 || response.status === 205) {
    return null;
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

export const api = {
  getHealth: () => requestJson('/health'),
  getWorkflowSpec: () => requestJson('/workflow/spec'),
  listProjects: () => requestJson('/projects'),
  createProject: (payload) => requestJson('/projects', { method: 'POST', body: payload }),
  updateProject: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}`, { method: 'PUT', body: payload }),
  deleteProject: (projectId) => requestJson(`/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' }),
  deleteProjectArtifact: (projectId, artifactKey) => requestJson(`/projects/${encodeURIComponent(projectId)}/artifacts/${encodeURIComponent(artifactKey)}`, { method: 'DELETE' }),
  completeField: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/field-completion`, { method: 'POST', body: payload }),
  getProject: (projectId) => requestJson(`/projects/${encodeURIComponent(projectId)}`),
  getProjectSnapshot: (projectId) => requestJson(`/projects/${encodeURIComponent(projectId)}/snapshot`),
  listTasks: (projectId) => requestJson(`/projects/${encodeURIComponent(projectId)}/tasks`),
  getTask: (taskId) => requestJson(`/tasks/${encodeURIComponent(taskId)}`),
  cancelTask: (taskId) => requestJson(`/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' }),
  runRequirements: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/requirements`, { method: 'POST', body: payload }),
  runStoryBible: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/story-bible`, { method: 'POST', body: payload }),
  runCharacters: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/characters`, { method: 'POST', body: payload }),
  runOutline: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/outline`, { method: 'POST', body: payload }),
  runVolumeOutline: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/volume-outline`, { method: 'POST', body: payload }),
  runChapterPlan: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/chapter-plan`, { method: 'POST', body: payload }),
  runChapter: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/chapters`, { method: 'POST', body: payload }),
  runRevision: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/revision`, { method: 'POST', body: payload }),
  runConsistency: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/consistency`, { method: 'POST', body: payload }),
  runMemory: (projectId, payload) => requestJson(`/projects/${encodeURIComponent(projectId)}/memory`, { method: 'POST', body: payload }),
};

export async function waitForTask(taskId, { intervalMs = 1200, timeoutMs = 10 * 60 * 1000 } = {}) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const task = await api.getTask(taskId);
    if (task.status !== 'pending' && task.status !== 'running') {
      return task;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`任务 ${taskId} 超时`);
}
