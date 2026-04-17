import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, PAGE_STEP_GROUPS, getArtifact, getFieldDisplayValue, getStepLabel, getStepMeta, getStepStatus, loadWorkflowContext } from './app-config.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderNotice, summarizeList } from './dom.js';
import { getPageProjectId, getPreferredStep, setPreferredStep, setSelectedProjectId, syncProjectId, syncTopNavLinks, withProjectQuery } from './state.js';
import { deleteStepArtifact, hydrateVolumeOutlineDefaults, renderArtifactBlock, renderChecklist, renderDependencyList, renderStageOverview, renderTaskList, renderField, runFieldCompletion, runStepFromForm } from './workspace-utils.js';

const projectMini = document.getElementById('outline-project-mini');
const tree = document.getElementById('outline-tree');
const overview = document.getElementById('outline-overview');
const workspace = document.getElementById('outline-workspace');
const workspaceTitle = document.getElementById('outline-workspace-title');
const inspector = document.getElementById('outline-inspector');
const reloadButton = document.getElementById('reload-outline');

const PAGE_KEY = 'outline';
const VISIBLE_STEPS = PAGE_STEP_GROUPS.outline.flatMap((group) => group.steps);

let workflowSteps = FALLBACK_WORKFLOW_STEPS;
let dependencyMap = Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []]));
let currentSnapshot = null;
let currentTasks = [];
let currentStep = '';

function pickDefaultStep() {
  const preferred = getPreferredStep(PAGE_KEY);
  if (preferred && VISIBLE_STEPS.includes(preferred)) {
    return preferred;
  }
  return VISIBLE_STEPS.find((step) => !getArtifact(currentSnapshot, step)) || VISIBLE_STEPS[0];
}

function renderProjectMini(snapshot) {
  if (!snapshot) {
    renderEmpty(projectMini, '请先在项目台选择一个项目。');
    return;
  }
  const project = snapshot.project;
  projectMini.innerHTML = `
    <div class="context-card">
      <div class="context-head">
        <div>
          <p class="eyebrow">结构目标</p>
          <h3>${escapeHtml(project.input.title)}</h3>
        </div>
        ${badge(project.status, 'accent')}
      </div>
      <div class="chips">
        ${badge(`${project.input.target_volume_count} 卷`, 'soft')}
        ${badge(`${project.input.target_chapters_per_volume} 章/卷`, 'soft')}
        ${badge(`${project.input.target_words} 字`, 'soft')}
      </div>
      <p class="muted">总纲关注：${escapeHtml(summarizeList(project.input.outline_focus))}</p>
    </div>
  `;
}

function renderTree() {
  tree.innerHTML = `
    <div class="tree-list">
      ${VISIBLE_STEPS.map((step, index) => {
        const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks);
        return `
          <button type="button" class="tree-node ${step === currentStep ? 'active' : ''}" data-step-node="${step}">
            <div>
              <p class="eyebrow">节点 ${index + 1}</p>
              <h3>${escapeHtml(getStepMeta(step).objectName || getStepLabel(step, workflowSteps))}</h3>
              <p class="muted">${escapeHtml(getStepMeta(step).description || '')}</p>
            </div>
            ${badge(status.text, status.tone)}
          </button>
        `;
      }).join('')}
    </div>
    <div class="context-card subtle">
      <p class="eyebrow">结构提醒</p>
      <h3>总纲、卷纲、章节计划分层确认</h3>
      <p class="muted">总纲先产出各卷粗纲和粗章节计划，卷纲和章节计划都先走粗稿确认，再进入完整细化。</p>
    </div>
  `;

  tree.querySelectorAll('[data-step-node]').forEach((button) => {
    button.addEventListener('click', () => {
      const step = button.getAttribute('data-step-node');
      if (!step) {
        return;
      }
      currentStep = step;
      setPreferredStep(PAGE_KEY, step);
      renderTree();
      renderWorkspace();
      renderInspector();
    });
  });
}

function buildStepForm(step) {
  const project = currentSnapshot?.project;
  const meta = getStepMeta(step);
  const fields = (meta.fields || []).map((field) => ({ ...field, stepKey: step }));
  const primaryFields = fields.filter((field) => !field.advanced);
  const advancedFields = fields.filter((field) => field.advanced);

  return `
    <form class="workspace-form" data-step-form="${step}">
      <div class="form-grid">
        ${primaryFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot))).join('')}
      </div>
      ${advancedFields.length ? `
        <details class="advanced-panel">
          <summary>高级设置</summary>
          <div class="form-grid compact-grid">
            ${advancedFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot))).join('')}
          </div>
        </details>
      ` : ''}
      <div class="actions-row wrap">
        <button class="primary" type="submit">执行当前结构节点</button>
        <button class="ghost" type="button" data-delete-step="${step}" ${getArtifact(currentSnapshot, step) ? '' : 'disabled'}>删除当前结构产物</button>
      </div>
      <div class="notice info" data-step-message hidden></div>
    </form>
  `;
}

function renderWorkspace() {
  if (!currentSnapshot) {
    renderEmpty(workspace, '未选择项目。');
    return;
  }
  const step = currentStep;
  const meta = getStepMeta(step);
  const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks);
  workspaceTitle.textContent = `${meta.label} · ${meta.objectName}`;
  overview.innerHTML = renderStageOverview(VISIBLE_STEPS, currentSnapshot, dependencyMap, currentTasks);
  workspace.innerHTML = `
    <section class="workspace-card">
      <div class="workspace-card-head">
        <div>
          <p class="eyebrow">结构节点</p>
          <h3>${escapeHtml(meta.objectName || meta.label)}</h3>
          <p class="muted">${escapeHtml(meta.description || '')}</p>
        </div>
        ${badge(status.text, status.tone)}
      </div>
      <div class="workspace-card-grid">
        <div>${buildStepForm(step)}</div>
        <div>${renderArtifactBlock(currentSnapshot, step)}</div>
      </div>
    </section>
  `;

  const form = workspace.querySelector('[data-step-form]');
  const messageBox = workspace.querySelector('[data-step-message]');
  const deleteButton = workspace.querySelector('[data-delete-step]');

  if (step === 'volume_outline') {
    hydrateVolumeOutlineDefaults(form, currentSnapshot);
  }

  form.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-ai-complete]');
    if (!button || !form.contains(button)) {
      return;
    }
    event.preventDefault();
    button.disabled = true;
    try {
      await runFieldCompletion({
        projectId: currentSnapshot.project.project_id,
        step,
        form,
        button,
        onProgress(message) {
          messageBox.hidden = false;
          messageBox.className = 'notice info';
          messageBox.textContent = message;
        },
      });
    } catch (error) {
      messageBox.hidden = false;
      messageBox.className = 'notice error';
      messageBox.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await runStepFromForm({
        projectId: currentSnapshot.project.project_id,
        step,
        form,
        onProgress(message) {
          messageBox.hidden = false;
          messageBox.className = 'notice info';
          messageBox.textContent = message;
        },
      });
      await loadPage();
    } catch (error) {
      messageBox.hidden = false;
      messageBox.className = 'notice error';
      messageBox.textContent = error.message;
    }
  });

  deleteButton.addEventListener('click', async () => {
    try {
      const result = await deleteStepArtifact({
        projectId: currentSnapshot.project.project_id,
        step,
        label: meta.objectName || meta.label,
      });
      if (!result) {
        return;
      }
      await loadPage();
    } catch (error) {
      messageBox.hidden = false;
      messageBox.className = 'notice error';
      messageBox.textContent = error.message;
    }
  });
}

function renderInspector() {
  if (!currentSnapshot) {
    renderEmpty(inspector, '暂无结构审查内容。');
    return;
  }
  const project = currentSnapshot.project;
  const stepTasks = currentTasks.filter((task) => task.task_name === currentStep);
  inspector.innerHTML = `
    <div class="stack-list">
      <section class="context-card">
        <p class="eyebrow">结构范围</p>
        <h3>${escapeHtml(project.input.title)}</h3>
        <p class="muted">更新时间 ${escapeHtml(formatDate(project.updated_at))}</p>
      </section>

      <section class="context-card">
        <p class="eyebrow">依赖检查</p>
        <h3>${escapeHtml(getStepMeta(currentStep).objectName || '')}</h3>
        ${renderDependencyList(currentStep, dependencyMap, currentSnapshot)}
      </section>

      <section class="context-card">
        <p class="eyebrow">结构审查清单</p>
        <h3>${escapeHtml(getStepLabel(currentStep, workflowSteps))}</h3>
        ${renderChecklist(currentStep)}
      </section>

      <section class="context-card">
        <p class="eyebrow">最近任务</p>
        <h3>结构执行记录</h3>
        ${renderTaskList(stepTasks, { limit: 5 })}
      </section>

      <section class="context-card subtle">
        <p class="eyebrow">联动入口</p>
        <h3>去设定与写作 / 审查台</h3>
        <div class="actions-row wrap">
          <a class="secondary-link" href="${withProjectQuery('/workflow', project.project_id)}">设定与写作</a>
          <a class="secondary-link" href="${withProjectQuery('/review', project.project_id)}">审查台</a>
        </div>
      </section>
    </div>
  `;
}

async function loadPage() {
  const projectId = getPageProjectId();
  if (!projectId) {
    renderEmpty(workspace, '未选择项目。请先去项目台选择一个项目。');
    renderEmpty(projectMini, '未选择项目。');
    overview.innerHTML = '';
    inspector.innerHTML = '';
    tree.innerHTML = '';
    return;
  }

  syncProjectId(projectId);
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
  setSelectedProjectId(projectId);

  currentStep = VISIBLE_STEPS.includes(currentStep) ? currentStep : pickDefaultStep();
  renderProjectMini(snapshot);
  renderTree();
  renderWorkspace();
  renderInspector();
}

async function init() {
  reloadButton.addEventListener('click', async () => {
    try {
      await loadPage();
    } catch (error) {
      renderNotice(workspace, error.message, 'error');
    }
  });

  try {
    await loadPage();
  } catch (error) {
    renderNotice(workspace, error.message, 'error');
  }
}

window.addEventListener('DOMContentLoaded', init);
