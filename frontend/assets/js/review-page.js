import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, REVIEW_GROUPS, getArtifact, getStepDependencies, getStepLabel, getStepMeta, getStepStatus, isUnlocked, loadWorkflowContext } from './app-config.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderJsonPreview, renderNotice, truncate } from './dom.js';
import { getPageProjectId, setSelectedProjectId, syncTopNavLinks, withProjectQuery } from './state.js';

const summary = document.getElementById('review-summary');
const queue = document.getElementById('review-queue');
const actions = document.getElementById('review-actions');
const matrix = document.getElementById('review-matrix');
const taskList = document.getElementById('review-tasks');
const reloadButton = document.getElementById('reload-review');

let workflowSteps = FALLBACK_WORKFLOW_STEPS;
let dependencyMap = Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []]));
let currentSnapshot = null;
let currentTasks = [];

function buildIssueQueue(snapshot, tasks) {
  const issues = [];
  for (const stepDef of workflowSteps) {
    const step = stepDef.key;
    const artifact = getArtifact(snapshot, step);
    const latestTask = [...tasks].filter((task) => task.task_name === step).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

    if (latestTask?.status === 'failed') {
      issues.push({
        severity: '高',
        tone: 'danger',
        title: `${getStepLabel(step, workflowSteps)}执行失败`,
        detail: latestTask.error || '最近一次执行失败，需要先处理这个错误。',
        page: getStepMeta(step).page,
        step,
      });
      continue;
    }

    if (!artifact && isUnlocked(step, snapshot, dependencyMap)) {
      issues.push({
        severity: step === 'chapter' ? '高' : '中',
        tone: step === 'chapter' ? 'danger' : 'warn',
        title: `${getStepLabel(step, workflowSteps)}待处理`,
        detail: `前置依赖已经齐了，但这个对象还没有产物。`,
        page: getStepMeta(step).page,
        step,
      });
    }
  }

  if (getArtifact(snapshot, 'chapter') && !getArtifact(snapshot, 'consistency')) {
    issues.push({
      severity: '中',
      tone: 'warn',
      title: '正文已出，但一致性检查缺失',
      detail: '角色、设定和正文之间还没有交叉检查结果。',
      page: 'workflow',
      step: 'consistency',
    });
  }

  if (getArtifact(snapshot, 'chapter') && !getArtifact(snapshot, 'revision')) {
    issues.push({
      severity: '中',
      tone: 'warn',
      title: '正文已出，但缺少修订版本',
      detail: '建议至少做一轮节奏、文风或信息密度修订。',
      page: 'workflow',
      step: 'revision',
    });
  }

  return issues.slice(0, 8);
}

function renderSummary(snapshot, tasks) {
  const project = snapshot.project;
  const artifactCount = Object.keys(snapshot.artifacts || {}).length;
  const failedTasks = tasks.filter((task) => task.status === 'failed').length;
  const pendingTasks = tasks.filter((task) => task.status === 'pending' || task.status === 'running').length;

  summary.innerHTML = `
    <div class="stats-grid">
      <article class="stat-card"><div class="stat-number">${escapeHtml(artifactCount)}</div><div class="muted">已产出对象</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(failedTasks)}</div><div class="muted">失败任务</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(pendingTasks)}</div><div class="muted">执行中任务</div></article>
      <article class="stat-card"><div class="stat-number">${escapeHtml(workflowSteps.length - artifactCount)}</div><div class="muted">尚未产出的对象</div></article>
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
        <a class="secondary-link" href="${withProjectQuery(item.page === 'outline' ? '/outline' : '/workflow', projectId)}">去处理</a>
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
          <a class="primary-link" href="${withProjectQuery(recommended?.page === 'outline' ? '/outline' : '/workflow', projectId)}">打开主处理页面</a>
          <a class="secondary-link" href="${withProjectQuery('/workflow', projectId)}">设定与写作</a>
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
          const status = getStepStatus(step, snapshot, dependencyMap, currentTasks);
          const artifact = getArtifact(snapshot, step);
          const deps = getStepDependencies(step, dependencyMap);
          const link = getStepMeta(step).page === 'outline' ? '/outline' : '/workflow';
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
                <a class="secondary-link" href="${withProjectQuery(link, projectId)}">打开对象</a>
                ${artifact ? `<button class="ghost danger" type="button" data-delete-artifact="${step}">删除产物</button>` : ''}
              </div>
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `).join('');

  matrix.querySelectorAll('[data-delete-artifact]').forEach((button) => {
    button.addEventListener('click', async () => {
      const step = button.getAttribute('data-delete-artifact');
      if (!step) {
        return;
      }
      const confirmed = window.confirm(`删除“${getStepLabel(step, workflowSteps)}”后，依赖它的下游对象也会被清理，是否继续？`);
      if (!confirmed) {
        return;
      }
      await api.deleteProjectArtifact(projectId, step);
      await loadPage();
    });
  });
}

function renderTasks(tasks) {
  if (!tasks.length) {
    renderEmpty(taskList, '当前项目还没有任务记录。');
    return;
  }
  const recent = [...tasks].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 12);
  taskList.innerHTML = recent.map((task) => `
    <article class="task-card">
      <div class="task-card-head">
        ${badge(task.status, task.status === 'failed' ? 'danger' : task.status === 'completed' ? 'success' : 'accent')}
        ${badge(task.task_name, 'soft')}
        ${badge(task.task_id, 'soft')}
      </div>
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

  const issues = buildIssueQueue(snapshot, tasks);
  renderSummary(snapshot, tasks);
  renderQueueItems(issues, projectId);
  renderActionsPanel(issues, projectId);
  renderMatrix(snapshot, projectId);
  renderTasks(tasks);
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
