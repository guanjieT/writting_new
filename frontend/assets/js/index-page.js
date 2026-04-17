import { api } from './api-client.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderJsonPreview, renderNotice, summarizeList, truncate } from './dom.js';
import { getSelectedProjectId, setSelectedProjectId, syncTopNavLinks, withProjectQuery } from './state.js';

const FORM_SECTIONS = [
  {
    title: '作品定位',
    hint: '先把题材、核心前提和目标受众说清楚。',
    fields: [
      { key: 'title', label: '项目标题', type: 'text', required: true },
      { key: 'genre', label: '题材', type: 'text', required: true },
      { key: 'premise', label: '一句话前提', type: 'textarea', rows: 4 },
      { key: 'target_audience', label: '目标受众', type: 'text' },
    ],
  },
  {
    title: '规模与节奏',
    hint: '这些字段决定后续总纲和章节计划的默认建议值。',
    fields: [
      { key: 'target_words', label: '目标字数', type: 'number', value: 80000 },
      { key: 'target_volume_count', label: '目标卷数', type: 'number', value: 1 },
      { key: 'target_chapters_per_volume', label: '每卷章节数', type: 'number', value: 12 },
    ],
  },
  {
    title: '风格与约束',
    hint: '一行一条即可，前端会自动转成数组。',
    fields: [
      { key: 'tone', label: '气质 / 氛围', type: 'textarea', rows: 4, list: true },
      { key: 'style', label: '风格要求', type: 'textarea', rows: 4, list: true },
      { key: 'outline_focus', label: '总纲关注点', type: 'textarea', rows: 4, list: true },
      { key: 'core_requirements', label: '核心要求', type: 'textarea', rows: 5, list: true },
      { key: 'forbidden_elements', label: '禁忌元素', type: 'textarea', rows: 5, list: true },
    ],
  },
];

const form = document.getElementById('project-form');
const projectList = document.getElementById('project-list');
const selectedProjectSummary = document.getElementById('selected-project-summary');
const projectDashboard = document.getElementById('project-dashboard');
const refreshButton = document.getElementById('refresh-projects');
const newProjectButton = document.getElementById('new-project-mode');
const submitButton = document.querySelector('button[form="project-form"]');

const FORM_FIELD_NAMES = new Set([
  'title',
  'genre',
  'premise',
  'target_audience',
  'target_words',
  'target_volume_count',
  'target_chapters_per_volume',
  'tone',
  'style',
  'outline_focus',
  'core_requirements',
  'forbidden_elements',
]);

function buildForm() {
  form.innerHTML = FORM_SECTIONS.map((section) => `
    <section class="wizard-section">
      <div class="wizard-section-head">
        <h3>${escapeHtml(section.title)}</h3>
        <p class="muted">${escapeHtml(section.hint)}</p>
      </div>
      <div class="form-grid">
        ${section.fields.map((field) => fieldMarkup(field)).join('')}
      </div>
    </section>
  `).join('');
}

function setFormMode(project) {
  if (!submitButton) {
    return;
  }
  submitButton.textContent = project ? '保存当前项目' : '创建并设为当前项目';
}

function populateForm(project) {
  if (!form || !project) {
    return;
  }
  const input = project.input || {};
  for (const field of FORM_FIELD_NAMES) {
    const control = form.elements.namedItem(field);
    if (!control) {
      continue;
    }
    const value = input[field];
    if (Array.isArray(value)) {
      control.value = value.join('\n');
    } else if (value !== undefined && value !== null) {
      control.value = String(value);
    } else if (field === 'target_words') {
      control.value = '80000';
    } else if (field === 'target_volume_count') {
      control.value = '1';
    } else if (field === 'target_chapters_per_volume') {
      control.value = '12';
    } else {
      control.value = '';
    }
  }
  setFormMode(project);
}

function resetFormToCreateMode() {
  form.reset();
  setFormMode(null);
}

function fieldMarkup(field) {
  const value = field.value ?? '';
  if (field.type === 'textarea') {
    return `
      <div class="field full">
        <label for="${field.key}">${escapeHtml(field.label)}</label>
        <textarea name="${field.key}" rows="${field.rows || 4}" ${field.required ? 'required' : ''}>${escapeHtml(value)}</textarea>
      </div>
    `;
  }
  return `
    <div class="field">
      <label for="${field.key}">${escapeHtml(field.label)}</label>
      <input name="${field.key}" type="${field.type}" value="${escapeHtml(String(value))}" ${field.required ? 'required' : ''} />
    </div>
  `;
}

function readPayload() {
  const formData = new FormData(form);
  const payload = {};
  for (const section of FORM_SECTIONS) {
    for (const field of section.fields) {
      const raw = formData.get(field.key);
      if (field.list) {
        payload[field.key] = String(raw || '').split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
      } else if (field.type === 'number') {
        payload[field.key] = Number(raw || field.value || 0);
      } else {
        payload[field.key] = String(raw || '').trim();
      }
    }
  }
  return payload;
}

function buildDashboard(projects, currentProject) {
  const total = projects.length;
  const active = currentProject ? 1 : 0;
  const generatedProjects = projects.filter((project) => Object.keys(project.artifacts || {}).length > 0).length;
  const avgArtifacts = total ? (projects.reduce((sum, item) => sum + Object.keys(item.artifacts || {}).length, 0) / total).toFixed(1) : '0.0';

  projectDashboard.innerHTML = `
    <div class="stats-grid">
      <article class="stat-card"><div class="stat-number">${escapeHtml(total)}</div><div class="muted">项目总数</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(generatedProjects)}</div><div class="muted">已有产物的项目</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(avgArtifacts)}</div><div class="muted">平均产物数</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(active)}</div><div class="muted">当前选中</div></article>
    </div>
    ${currentProject ? `
      <div class="context-card">
        <div class="context-head">
          <div>
            <p class="eyebrow">当前工程</p>
            <h3>${escapeHtml(currentProject.input.title)}</h3>
          </div>
          ${badge(currentProject.status, 'accent')}
        </div>
        <p>${escapeHtml(truncate(currentProject.input.premise || '暂无一句话前提', 140))}</p>
        <div class="chips">
          ${badge(currentProject.input.genre, 'soft')}
          ${badge(`${currentProject.input.target_words} 字`, 'soft')}
          ${badge(`${currentProject.input.target_volume_count} 卷`, 'soft')}
        </div>
      </div>
    ` : '<div class="empty-state compact">还没有选中的项目。</div>'}
  `;
}

function renderSelectedProject(project) {
  if (!project) {
    renderEmpty(selectedProjectSummary, '还没有选中项目。先从下方项目列表选择，或者直接创建一个新项目。');
    setFormMode(null);
    return;
  }

  const artifactCount = Object.keys(project.artifacts || {}).length;
  selectedProjectSummary.innerHTML = `
    <div class="context-card">
      <div class="context-head">
        <div>
          <p class="eyebrow">活动项目</p>
          <h3>${escapeHtml(project.input.title)}</h3>
        </div>
        ${badge(project.status, 'accent')}
      </div>
      <p class="muted">更新时间 ${escapeHtml(formatDate(project.updated_at))}</p>
      <div class="chips">
        ${badge(project.project_id, 'soft')}
        ${badge(`${artifactCount} 个产物`, artifactCount ? 'success' : 'soft')}
        ${badge(project.input.genre, 'soft')}
      </div>
      <p>${escapeHtml(truncate(project.input.premise || '暂无前提描述', 140))}</p>
      <div class="actions-row wrap">
        <a class="primary-link" href="${withProjectQuery('/workflow', project.project_id)}">去设定与写作</a>
        <a class="secondary-link" href="${withProjectQuery('/outline', project.project_id)}">去结构台</a>
        <a class="secondary-link" href="${withProjectQuery('/review', project.project_id)}">去审查台</a>
      </div>
      <details>
        <summary>查看项目原始数据</summary>
        ${renderJsonPreview(project)}
      </details>
    </div>
  `;
}

function renderProjectCard(project) {
  const selected = project.project_id === getSelectedProjectId();
  const artifactCount = Object.keys(project.artifacts || {}).length;
  return `
    <article class="project-card ${selected ? 'selected' : ''}">
      <div class="project-card-head">
        <div>
          <h3>${escapeHtml(project.input.title)}</h3>
          <p class="muted">${escapeHtml(project.input.genre)} · ${escapeHtml(project.input.target_words)} 字 · ${escapeHtml(project.input.target_volume_count)} 卷</p>
        </div>
        ${badge(selected ? '当前项目' : project.status, selected ? 'accent' : 'soft')}
      </div>
      <p>${escapeHtml(truncate(project.input.premise || '暂无前提描述', 130))}</p>
      <div class="chips">
        ${badge(`${artifactCount} 个产物`, artifactCount ? 'success' : 'soft')}
        ${badge(`风格：${summarizeList(project.input.style)}`, 'soft')}
        ${badge(`气质：${summarizeList(project.input.tone)}`, 'soft')}
      </div>
      <div class="actions-row wrap">
        <button class="secondary" type="button" data-select-project="${escapeHtml(project.project_id)}">设为当前</button>
        <a class="secondary-link" href="${withProjectQuery('/workflow', project.project_id)}">设定与写作</a>
        <a class="secondary-link" href="${withProjectQuery('/outline', project.project_id)}">结构台</a>
        <a class="secondary-link" href="${withProjectQuery('/review', project.project_id)}">审查台</a>
        <button class="ghost danger" type="button" data-delete-project="${escapeHtml(project.project_id)}">删除</button>
      </div>
    </article>
  `;
}

async function loadProjects() {
  const projects = await api.listProjects();
  const selectedProjectId = getSelectedProjectId();
  const currentProject = selectedProjectId ? projects.find((item) => item.project_id === selectedProjectId) || null : null;

  buildDashboard(projects, currentProject);
  renderSelectedProject(currentProject);
  if (currentProject) {
    populateForm(currentProject);
  } else {
    resetFormToCreateMode();
  }

  if (!projects.length) {
    renderEmpty(projectList, '暂时还没有项目。先在左侧创建一个作品工程。');
    return;
  }

  projectList.innerHTML = projects.map(renderProjectCard).join('');

  projectList.querySelectorAll('[data-select-project]').forEach((button) => {
    button.addEventListener('click', async () => {
      const projectId = button.getAttribute('data-select-project');
      setSelectedProjectId(projectId || '');
      await loadProjects();
    });
  });

  projectList.querySelectorAll('[data-delete-project]').forEach((button) => {
    button.addEventListener('click', async () => {
      const projectId = button.getAttribute('data-delete-project');
      if (!projectId) {
        return;
      }
      const confirmed = window.confirm('删除项目会同时移除该项目下所有产物和任务记录，确定继续吗？');
      if (!confirmed) {
        return;
      }
      await api.deleteProject(projectId);
      if (projectId === getSelectedProjectId()) {
        setSelectedProjectId('');
      }
      await loadProjects();
    });
  });
}

async function init() {
  buildForm();
  syncTopNavLinks();

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = document.querySelector('button[form="project-form"]');
    submitButton.disabled = true;
    try {
      const projectId = getSelectedProjectId();
      const payload = readPayload();
      const project = projectId
        ? await api.updateProject(projectId, payload)
        : await api.createProject(payload);
      setSelectedProjectId(project.project_id);
      syncTopNavLinks(project.project_id);
      await loadProjects();
    } catch (error) {
      renderNotice(selectedProjectSummary, error.message, 'error');
    } finally {
      submitButton.disabled = false;
    }
  });

  if (newProjectButton) {
    newProjectButton.addEventListener('click', () => {
      setSelectedProjectId('');
      syncTopNavLinks('');
      resetFormToCreateMode();
      renderSelectedProject(null);
      loadProjects().catch((error) => renderNotice(projectDashboard, error.message, 'error'));
    });
  }

  refreshButton.addEventListener('click', async () => {
    try {
      await loadProjects();
    } catch (error) {
      renderNotice(projectDashboard, error.message, 'error');
    }
  });

  try {
    await loadProjects();
  } catch (error) {
    renderNotice(projectDashboard, error.message, 'error');
  }
}

window.addEventListener('DOMContentLoaded', init);
