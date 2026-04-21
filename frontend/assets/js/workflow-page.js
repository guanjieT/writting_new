import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, PAGE_STEP_GROUPS, getArtifact, getFieldDisplayValue, getStepDependencies, getStepLabel, getStepMeta, getStepStatus, isUnlocked, loadWorkflowContext } from './app-config.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderJsonPreview, renderNotice, summarizeList, truncate } from './dom.js';
import { getPageProjectId, getPreferredStep, setPreferredStep, setSelectedProjectId, syncProjectId, syncTopNavLinks, withProjectQuery } from './state.js';
import { deleteStepArtifact, hydrateVolumeOutlineDefaults, renderArtifactBlock, renderChecklist, renderDependencyList, renderStageOverview, renderTaskList, renderField, runFieldCompletion, runStepFromForm } from './workspace-utils.js';

const projectMini = document.getElementById('workflow-project-mini');
const stageGroups = document.getElementById('workflow-stage-groups');
const workspaceTitle = document.getElementById('workflow-workspace-title');
const workspace = document.getElementById('workflow-workspace');
const inspector = document.getElementById('workflow-inspector');
const overview = document.getElementById('workflow-overview');
const reloadButton = document.getElementById('reload-workflow');
const jumpOutlineLink = document.getElementById('jump-outline-link');

const PAGE_KEY = 'workflow';
const VISIBLE_STEPS = PAGE_STEP_GROUPS.workflow.flatMap((group) => group.steps);

let workflowSteps = FALLBACK_WORKFLOW_STEPS;
let dependencyMap = Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []]));
let currentSnapshot = null;
let currentTasks = [];
let currentStep = '';

function chooseDefaultStep() {
  const preferred = getPreferredStep(PAGE_KEY);
  if (preferred && VISIBLE_STEPS.includes(preferred)) {
    return preferred;
  }
  const unlocked = VISIBLE_STEPS.find((step) => isUnlocked(step, currentSnapshot, dependencyMap));
  return unlocked || VISIBLE_STEPS[0];
}

function renderProjectMini(snapshot) {
  if (!snapshot) {
    renderEmpty(projectMini, '请先回到项目台选择一个项目。');
    return;
  }
  const project = snapshot.project;
  projectMini.innerHTML = `
    <div class="context-card">
      <div class="context-head">
        <div>
          <p class="eyebrow">当前项目</p>
          <h3>${escapeHtml(project.input.title)}</h3>
        </div>
        ${badge(project.status, 'accent')}
      </div>
      <p class="muted">${escapeHtml(project.input.genre)} · ${escapeHtml(project.input.target_words)} 字</p>
      <div class="chips">
        ${badge(`${Object.keys(snapshot.artifacts || {}).length} 个产物`, 'soft')}
        ${badge(`${project.input.target_volume_count} 卷`, 'soft')}
        ${badge(`${project.input.target_chapters_per_volume} 章/卷`, 'soft')}
      </div>
    </div>
  `;
}

function renderStageNav() {
  stageGroups.innerHTML = PAGE_STEP_GROUPS.workflow.map((group) => `
    <section class="nav-section">
      <div class="nav-section-head">
        <h3>${escapeHtml(group.label)}</h3>
      </div>
      <div class="nav-list">
        ${group.steps.map((step) => {
          const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks);
          return `
            <button type="button" class="nav-item ${step === currentStep ? 'active' : ''}" data-select-step="${step}">
              <div>
                <strong>${escapeHtml(getStepLabel(step, workflowSteps))}</strong>
                <div class="muted">${escapeHtml(getStepMeta(step).objectName || '')}</div>
              </div>
              ${badge(status.text, status.tone)}
            </button>
          `;
        }).join('')}
      </div>
    </section>
  `).join('');

  stageGroups.querySelectorAll('[data-select-step]').forEach((button) => {
    button.addEventListener('click', () => {
      const step = button.getAttribute('data-select-step');
      if (!step) {
        return;
      }
      currentStep = step;
      setPreferredStep(PAGE_KEY, step);
      renderStageNav();
      renderWorkspace();
      renderInspector();
    });
  });
}

function buildStepForm(step) {
  const meta = getStepMeta(step);
  const project = currentSnapshot?.project;
  const fields = meta.fields || [];
  const primaryFields = fields.filter((field) => !field.advanced).map((field) => ({ ...field, stepKey: step }));
  const advancedFields = fields.filter((field) => field.advanced).map((field) => ({ ...field, stepKey: step }));

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
        <button class="primary" type="submit" data-run-step="${step}">${isUnlocked(step, currentSnapshot, dependencyMap) ? '执行当前对象' : '等待前置完成'}</button>
        <button class="ghost" type="button" data-delete-step="${step}" ${getArtifact(currentSnapshot, step) ? '' : 'disabled'}>删除当前产物</button>
        <span class="muted">删除会级联清理依赖此对象的下游内容。</span>
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
          <p class="eyebrow">当前对象</p>
          <h3>${escapeHtml(meta.label)}</h3>
          <p class="muted">${escapeHtml(meta.description || '')}</p>
        </div>
        ${badge(status.text, status.tone)}
      </div>
      <div class="workspace-card-grid">
        <div>
          ${buildStepForm(step)}
        </div>
        <div>
          ${renderArtifactBlock(currentSnapshot, step)}
        </div>
      </div>
    </section>
  `;

  const form = workspace.querySelector('[data-step-form]');
  const messageBox = workspace.querySelector('[data-step-message]');
  const runButton = workspace.querySelector('[data-run-step]');
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
    if (!isUnlocked(step, currentSnapshot, dependencyMap)) {
      messageBox.hidden = false;
      messageBox.className = 'notice error';
      messageBox.textContent = '前置对象还没准备好，请先完成依赖步骤。';
      return;
    }
    runButton.disabled = true;
    try {
      await runStepFromForm({
        projectId: currentSnapshot.project.project_id,
        step,
        form,
        snapshot: currentSnapshot,
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
    } finally {
      runButton.disabled = false;
    }
  });

  deleteButton.addEventListener('click', async () => {
    try {
      const artifact = getArtifact(currentSnapshot, step);
      const result = await deleteStepArtifact({
        projectId: currentSnapshot.project.project_id,
        artifactKey: artifact?.key,
        label: meta.label,
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
    renderEmpty(inspector, '暂无项目可审查。');
    return;
  }

  const project = currentSnapshot.project;
  const stepTasks = currentTasks.filter((task) => task.task_name === currentStep);
  inspector.innerHTML = `
    <div class="stack-list">
      <section class="context-card">
        <p class="eyebrow">项目上下文</p>
        <h3>${escapeHtml(project.input.title)}</h3>
        <p class="muted">更新于 ${escapeHtml(formatDate(project.updated_at))}</p>
        <div class="chips">
          ${badge(`风格：${summarizeList(project.input.style)}`, 'soft')}
          ${badge(`气质：${summarizeList(project.input.tone)}`, 'soft')}
        </div>
      </section>

      <section class="context-card">
        <p class="eyebrow">依赖检查</p>
        <h3>${escapeHtml(getStepLabel(currentStep, workflowSteps))}</h3>
        ${renderDependencyList(currentStep, dependencyMap, currentSnapshot)}
      </section>

      <section class="context-card">
        <p class="eyebrow">人工审查清单</p>
        <h3>${escapeHtml(getStepMeta(currentStep).objectName || '')}</h3>
        ${renderChecklist(currentStep)}
      </section>

      <section class="context-card">
        <p class="eyebrow">相关任务</p>
        <h3>最近执行</h3>
        ${renderTaskList(stepTasks, { limit: 5 })}
      </section>

      <section class="context-card subtle">
        <p class="eyebrow">联动入口</p>
        <h3>去结构台或审查台</h3>
        <div class="actions-row wrap">
          <a class="secondary-link" href="${withProjectQuery('/outline', project.project_id)}">结构台</a>
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
    stageGroups.innerHTML = '';
    return;
  }

  syncProjectId(projectId);
  jumpOutlineLink.href = withProjectQuery('/outline', projectId);
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

  currentStep = VISIBLE_STEPS.includes(currentStep) ? currentStep : chooseDefaultStep();
  renderProjectMini(snapshot);
  renderStageNav();
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
