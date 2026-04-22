import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, REVIEW_GROUPS, getStepDependencies, getStepLabel, getStepMeta, loadWorkflowContext } from './step-meta.js';
import { findLatestTaskForStep, getArtifactForStep, getStepStatus, getTasksForSelection, isUnlocked } from './artifact-selectors.js';
import { inferChapterCountForVolume } from './planning-defaults.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderJsonPreview, renderNotice, truncate } from './dom.js';
import { getPageProjectId, setSelectedProjectId, syncTopNavLinks, withProjectQuery } from './state.js';
import { clampScopeSelection, getStepScopeKind, readScopeSelectionFromUrl, selectionForStep, syncScopeSelectionToUrl } from './scope-utils.js';

const summary = document.getElementById('review-summary');
const selectionPanel = document.getElementById('review-selection');
const queue = document.getElementById('review-queue');
const actions = document.getElementById('review-actions');
const matrix = document.getElementById('review-matrix');
const taskList = document.getElementById('review-tasks');
const reloadButton = document.getElementById('reload-review');

let workflowSteps = FALLBACK_WORKFLOW_STEPS;
let dependencyMap = Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []]));
let currentSnapshot = null;
let currentTasks = [];
let currentSelection = readScopeSelectionFromUrl();

function buildStepUrl(step, projectId) {
  const meta = getStepMeta(step);
  const path = meta.page === 'outline' ? '/outline' : meta.page === 'volume-outline' ? '/volume-outline' : meta.page === 'chapter-plan' ? '/chapter-plan' : '/workflow';
  const url = new URL(path, window.location.origin);
  if (projectId) {
    url.searchParams.set('project_id', projectId);
  }
  const scopeKind = getStepScopeKind(step);
  if (scopeKind !== 'project') {
    url.searchParams.set('volume_index', String(currentSelection.volumeIndex));
  }
  if (scopeKind === 'chapter') {
    url.searchParams.set('chapter_index', String(currentSelection.chapterIndex));
  }
  return `${url.pathname}${url.search}`;
}

function selectionForCurrentStep(step) {
  return selectionForStep(step, currentSelection);
}

function workflowStepKeys() {
  return workflowSteps.map((step) => (typeof step === 'string' ? step : step?.key)).filter(Boolean);
}

function renderSelection(snapshot) {
  if (!snapshot) {
    return;
  }

  const project = snapshot.project;
  const volumeCount = Math.max(Number(project.input.target_volume_count || 1), 1);
  const chapterCount = Math.max(Number(inferChapterCountForVolume(snapshot, currentSelection.volumeIndex)), 1);
  const volumeOptions = Array.from({ length: volumeCount }, (_, index) => index + 1);
  const chapterOptions = Array.from({ length: chapterCount }, (_, index) => index + 1);

  selectionPanel.innerHTML = `
    <div class="context-card subtle">
      <p class="eyebrow">章节上下文</p>
      <h3>第 ${currentSelection.volumeIndex} 卷 · 第 ${currentSelection.chapterIndex} 章</h3>
      <div class="form-grid">
        <div class="field">
          <label for="review-volume-index">卷序号</label>
          <select id="review-volume-index" data-review-volume-index>
            ${volumeOptions.map((value) => `<option value="${value}" ${value === currentSelection.volumeIndex ? 'selected' : ''}>第 ${value} 卷</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label for="review-chapter-index">章节序号</label>
          <select id="review-chapter-index" data-review-chapter-index>
            ${chapterOptions.map((value) => `<option value="${value}" ${value === currentSelection.chapterIndex ? 'selected' : ''}>第 ${value} 章</option>`).join('')}
          </select>
        </div>
      </div>
      <p class="muted">章节类对象的状态、展示和删除都以这里的卷/章为准。</p>
    </div>
  `;

  selectionPanel.querySelectorAll('[data-review-volume-index], [data-review-chapter-index]').forEach((control) => {
    control.addEventListener('change', () => {
      currentSelection = clampScopeSelection(
        currentSnapshot,
        {
          volumeIndex: Number(selectionPanel.querySelector('[data-review-volume-index]')?.value || currentSelection.volumeIndex || 1) || 1,
          chapterIndex: Number(selectionPanel.querySelector('[data-review-chapter-index]')?.value || currentSelection.chapterIndex || 1) || 1,
        },
        { getChapterCountForVolume: inferChapterCountForVolume },
      );
      syncScopeSelectionToUrl(currentSelection);
      renderPage();
    });
  });
}

function renderPage() {
  const issueItems = buildIssueQueue(currentSnapshot, currentTasks);
  renderSummary(currentSnapshot, currentTasks);
  renderQueueItems(issueItems, currentSnapshot.project.project_id);
  renderActionsPanel(issueItems, currentSnapshot.project.project_id);
  renderMatrix(currentSnapshot, currentSnapshot.project.project_id);
  renderTasks(currentTasks);
  renderSelection(currentSnapshot);
}

function buildIssueQueue(snapshot, tasks) {
  const issues = [];
  for (const stepDef of workflowSteps) {
    const step = typeof stepDef === 'string' ? stepDef : stepDef.key;
    if (!step) {
      continue;
    }
    const selection = selectionForCurrentStep(step);
    const artifact = getArtifactForStep(snapshot, step, selection);
    const latestTask = findLatestTaskForStep(step, tasks, selection);

    if (latestTask?.status === 'failed') {
      issues.push({
        severity: '高',
        tone: 'danger',
        title: `${getStepLabel(step, workflowSteps)}执行失败`,
        detail: latestTask.error || '最近一次执行失败，需要先处理这个错误。',
        step,
      });
      continue;
    }

    if (!artifact && isUnlocked(step, snapshot, dependencyMap, selection)) {
      issues.push({
        severity: step === 'chapter' ? '高' : '中',
        tone: step === 'chapter' ? 'danger' : 'warn',
        title: `${getStepLabel(step, workflowSteps)}待处理`,
        detail: `前置依赖已经齐了，但这个对象还没有产物。`,
        step,
      });
    }
  }

  const chapterSelection = selectionForCurrentStep('chapter');
  if (getArtifactForStep(snapshot, 'chapter', chapterSelection) && !getArtifactForStep(snapshot, 'consistency', chapterSelection)) {
    issues.push({
      severity: '中',
      tone: 'warn',
      title: '正文已出，但一致性检查缺失',
      detail: '角色、设定和正文之间还没有交叉检查结果。',
      step: 'consistency',
    });
  }

  if (getArtifactForStep(snapshot, 'chapter', chapterSelection) && !getArtifactForStep(snapshot, 'revision', chapterSelection)) {
    issues.push({
      severity: '中',
      tone: 'warn',
      title: '正文已出，但缺少修订版本',
      detail: '建议至少做一轮节奏、文风或信息密度修订。',
      step: 'revision',
    });
  }

  return issues.slice(0, 8);
}

function renderSummary(snapshot, tasks) {
  const project = snapshot.project;
  const stepKeys = workflowStepKeys();
  const artifactCount = Object.keys(snapshot.artifacts || {}).length;
  const visibleArtifactCount = stepKeys.filter((step) => Boolean(getArtifactForStep(snapshot, step, selectionForCurrentStep(step)))).length;
  const scopedTasks = getTasksForSelection(tasks, workflowSteps, currentSelection);
  const failedTasks = scopedTasks.filter((task) => task.status === 'failed').length;
  const pendingTasks = scopedTasks.filter((task) => task.status === 'pending' || task.status === 'running').length;
  const missingContextCount = stepKeys.filter((step) => !getArtifactForStep(snapshot, step, selectionForCurrentStep(step))).length;
  const pendingContextSteps = stepKeys.filter((step) => {
    const selection = selectionForCurrentStep(step);
    return !getArtifactForStep(snapshot, step, selection) && isUnlocked(step, snapshot, dependencyMap, selection);
  }).length;

  summary.innerHTML = `
    <div class="stats-grid">
      <article class="stat-card"><div class="stat-number">${escapeHtml(workflowSteps.length)}</div><div class="muted">唯一步骤总数</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(artifactCount)}</div><div class="muted">实际 artifact 总数</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(visibleArtifactCount)}</div><div class="muted">当前上下文已产出</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(missingContextCount)}</div><div class="muted">当前上下文缺失对象数</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(pendingContextSteps)}</div><div class="muted">当前 selection 待处理步骤</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(failedTasks)}</div><div class="muted">当前上下文失败任务</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(pendingTasks)}</div><div class="muted">当前上下文执行中任务</div></article>
    </div>
    <div class="context-card">
      <div class="context-head">
        <div>
          <p class="eyebrow">当前项目</p>
          <h3>${escapeHtml(project.input.title)}</h3>
        </div>
        ${badge(project.status, 'accent')}
      </div>
      <p>${escapeHtml(truncate(project.input.premise || '暂无一句话前提', 160))}</p>
      <div class="chips">
        ${badge(project.input.genre, 'soft')}
        ${badge(`${project.input.target_words} 字`, 'soft')}
        ${badge(`${project.input.target_volume_count} 卷`, 'soft')}
        ${badge(`${project.input.target_chapters_per_volume} 章/卷`, 'soft')}
      </div>
      <details>
        <summary>查看项目快照</summary>
        ${renderJsonPreview(snapshot)}
      </details>
    </div>
  `;
}

function renderQueueItems(items, projectId) {
  if (!items.length) {
    renderEmpty(queue, '当前没有高优先级问题。可以去继续推进结构或正文。');
    return;
  }
  queue.innerHTML = items.map((item) => `
    <article class="queue-card ${item.tone}">
      <div class="queue-card-head">
        <div>
          <p class="eyebrow">${escapeHtml(item.severity)}优先级</p>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        ${badge(item.severity, item.tone)}
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <div class="actions-row wrap">
        <a class="secondary-link" href="${buildStepUrl(item.step, projectId)}">去处理</a>
      </div>
    </article>
  `).join('');
}

function renderActionsPanel(items, projectId) {
  const recommended = items[0];
  actions.innerHTML = `
    <div class="stack-list">
      <section class="context-card">
        <p class="eyebrow">推荐入口</p>
        <h3>${escapeHtml(recommended ? recommended.title : '继续推进项目')}</h3>
        <p class="muted">${escapeHtml(recommended ? recommended.detail : '没有明显阻塞项，可以继续往下生成或进行人工审读。')}</p>
        <div class="actions-row wrap">
          <a class="primary-link" href="${buildStepUrl(recommended?.step || 'workflow', projectId)}">打开主处理页面</a>
          <a class="secondary-link" href="${withProjectQuery('/workflow', projectId)}">主工作流</a>
          <a class="secondary-link" href="${withProjectQuery('/outline', projectId)}">结构台</a>
        </div>
      </section>
      <section class="context-card subtle">
        <p class="eyebrow">审查原则</p>
        <ul class="checklist">
          <li>先查是否缺对象，再查对象质量。</li>
          <li>先查结构闭环，再查正文细节。</li>
          <li>删除上游对象前，先确认下游是否需要一起失效。</li>
        </ul>
      </section>
    </div>
  `;
}

function renderMatrix(snapshot, projectId) {
  matrix.innerHTML = REVIEW_GROUPS.map((group) => `
    <section class="review-group">
      <div class="review-group-head">
        <h3>${escapeHtml(group.label)}</h3>
      </div>
      <div class="review-group-grid">
        ${group.steps.map((step) => {
          const selection = selectionForCurrentStep(step);
          const status = getStepStatus(step, snapshot, dependencyMap, currentTasks, selection);
          const artifact = getArtifactForStep(snapshot, step, selection);
          const deps = getStepDependencies(step, dependencyMap);
          return `
            <article class="review-card">
              <div class="review-card-head">
                <div>
                  <p class="eyebrow">${escapeHtml(getStepMeta(step).objectName || step)}</p>
                  <h4>${escapeHtml(getStepLabel(step, workflowSteps))}</h4>
                </div>
                ${badge(status.text, status.tone)}
              </div>
              <p class="muted">依赖：${escapeHtml(deps.length ? deps.map((item) => getStepLabel(item, workflowSteps)).join(' → ') : '无')}</p>
              <p>${escapeHtml(truncate(artifact?.content || '尚未生成结果。', 120))}</p>
              <div class="actions-row wrap">
                <a class="secondary-link" href="${buildStepUrl(step, projectId)}">打开对象</a>
                ${artifact ? `<button class="ghost danger" type="button" data-delete-artifact-key="${artifact.key}" data-artifact-title="${escapeHtml(artifact.title || getStepLabel(step, workflowSteps))}">删除产物</button>` : ''}
              </div>
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `).join('');

  matrix.querySelectorAll('[data-delete-artifact-key]').forEach((button) => {
    button.addEventListener('click', async () => {
      const artifactKey = button.getAttribute('data-delete-artifact-key');
      if (!artifactKey) {
        return;
      }
      const confirmed = window.confirm(`删除“${button.getAttribute('data-artifact-title') || '该产物'}”后，依赖它的下游对象也会被清理，是否继续？`);
      if (!confirmed) {
        return;
      }
      await api.deleteProjectArtifact(projectId, artifactKey);
      await loadPage();
    });
  });
}

function renderTasks(tasks) {
  const scopedTasks = getTasksForSelection(tasks, workflowSteps, currentSelection);
  if (!scopedTasks.length) {
    renderEmpty(taskList, '当前上下文还没有任务记录。');
    return;
  }
  const recent = [...scopedTasks].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 12);
  taskList.innerHTML = recent.map((task) => `
    <article class="task-card">
      <div class="task-card-head">
        ${badge(task.status, task.status === 'failed' ? 'danger' : task.status === 'completed' ? 'success' : 'accent')}
        ${badge(task.task_name, 'soft')}
        ${badge(task.task_id, 'soft')}
      </div>
      <div class="muted">范围：${escapeHtml(task.scope_kind || 'project')}${task.volume_index ? ` · 第 ${escapeHtml(task.volume_index)} 卷` : ''}${task.chapter_index ? ` · 第 ${escapeHtml(task.chapter_index)} 章` : ''}</div>
      <div class="muted">创建于 ${escapeHtml(formatDate(task.created_at))}</div>
      <div class="muted">开始 ${escapeHtml(formatDate(task.started_at))} · 结束 ${escapeHtml(formatDate(task.finished_at))}</div>
      ${task.error ? `<div class="notice error">${escapeHtml(task.error)}</div>` : ''}
      ${task.result ? `<details><summary>查看结果</summary>${renderJsonPreview(task.result)}</details>` : ''}
    </article>
  `).join('');
}

async function loadPage() {
  const projectId = getPageProjectId();
  if (!projectId) {
    renderEmpty(summary, '未选择项目。请先去项目台选定一个项目。');
    renderEmpty(queue, '暂无问题');
    renderEmpty(actions, '暂无动作');
    renderEmpty(matrix, '暂无对象');
    renderEmpty(taskList, '暂无任务');
    return;
  }

  setSelectedProjectId(projectId);
  syncTopNavLinks(projectId);
  const [context, snapshot, tasks] = await Promise.all([
    loadWorkflowContext(),
    api.getProjectSnapshot(projectId),
    api.listTasks(projectId),
  ]);

  workflowSteps = context.steps || FALLBACK_WORKFLOW_STEPS;
  dependencyMap = context.dependencies || dependencyMap;
  currentSnapshot = snapshot;
  currentTasks = tasks;
  currentSelection = clampScopeSelection(snapshot, readScopeSelectionFromUrl(), {
    getChapterCountForVolume: inferChapterCountForVolume,
  });
  syncScopeSelectionToUrl(currentSelection);

  renderPage();
}

async function init() {
  reloadButton.addEventListener('click', async () => {
    try {
      await loadPage();
    } catch (error) {
      renderNotice(summary, error.message, 'error');
    }
  });

  try {
    await loadPage();
  } catch (error) {
    renderNotice(summary, error.message, 'error');
  }
}

window.addEventListener('DOMContentLoaded', init);
