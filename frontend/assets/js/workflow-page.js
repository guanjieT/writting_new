import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, PAGE_STEP_GROUPS, getArtifact, getFieldDisplayValue, getScopedArtifact, getStepDependencies, getStepLabel, getStepMeta, getStepScopeKind, getStepStatus, isUnlocked, loadWorkflowContext } from './app-config.js';
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
let currentSelection = getWorkflowSelectionFromUrl();

function getWorkflowSelectionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return {
    volumeIndex: Math.max(Number(params.get('volume_index') || '1') || 1, 1),
    chapterIndex: Math.max(Number(params.get('chapter_index') || '1') || 1, 1),
  };
}

function syncWorkflowSelectionToUrl(selection) {
  const url = new URL(window.location.href);
  url.searchParams.set('volume_index', String(selection.volumeIndex || 1));
  url.searchParams.set('chapter_index', String(selection.chapterIndex || 1));
  window.history.replaceState({}, '', url);
}

function clampWorkflowSelection(snapshot, selection = {}) {
  const volumeCount = Math.max(Number(snapshot?.project?.input?.target_volume_count || 1), 1);
  const chapterCount = Math.max(Number(snapshot?.project?.input?.target_chapters_per_volume || 1), 1);
  return {
    volumeIndex: Math.min(Math.max(Number(selection.volumeIndex || selection.volume_index || 1) || 1, 1), volumeCount),
    chapterIndex: Math.min(Math.max(Number(selection.chapterIndex || selection.chapter_index || 1) || 1, 1), chapterCount),
  };
}

function selectionForStep(step) {
  return getStepScopeKind(step) === 'chapter' ? currentSelection : {};
}

function updateWorkflowSelection(nextSelection) {
  currentSelection = clampWorkflowSelection(currentSnapshot, nextSelection);
  syncWorkflowSelectionToUrl(currentSelection);
  renderPage();
}

function renderSelectionCard(snapshot) {
  if (!snapshot) {
    return '';
  }

  const project = snapshot.project;
  const volumeOptions = Array.from({ length: Math.max(Number(project.input.target_volume_count || 1), 1) }, (_, index) => index + 1);
  const chapterOptions = Array.from({ length: Math.max(Number(project.input.target_chapters_per_volume || 1), 1) }, (_, index) => index + 1);
  const scopedArtifact = getScopedArtifact(snapshot, currentStep, currentSelection);
  const stepScopeKind = getStepScopeKind(currentStep);

  return `
    <div class="context-card subtle">
      <p class="eyebrow">章节上下文</p>
      <h3>第 ${currentSelection.volumeIndex} 卷 · 第 ${currentSelection.chapterIndex} 章</h3>
      <div class="form-grid">
        <div class="field">
          <label for="workflow-volume-index">卷序号</label>
          <select id="workflow-volume-index" data-workflow-volume-index>
            ${volumeOptions.map((value) => `<option value="${value}" ${value === currentSelection.volumeIndex ? 'selected' : ''}>第 ${value} 卷</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label for="workflow-chapter-index">章节序号</label>
          <select id="workflow-chapter-index" data-workflow-chapter-index>
            ${chapterOptions.map((value) => `<option value="${value}" ${value === currentSelection.chapterIndex ? 'selected' : ''}>第 ${value} 章</option>`).join('')}
          </select>
        </div>
      </div>
      <p class="muted">${stepScopeKind === 'chapter' ? '当前步骤会按这个章节读写与删除。' : '切换到章节步骤后，会沿用这个上下文。'}</p>
      <div class="chips">
        ${badge(scopedArtifact ? '当前章节有对应产物' : '当前章节暂无产物', scopedArtifact ? 'success' : 'soft')}
      </div>
    </div>
  `;
}

function renderPage() {
  renderProjectMini(currentSnapshot);
  renderStageNav();
  renderWorkspace();
  renderInspector();
}

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
    ${renderSelectionCard(snapshot)}
  `;

  projectMini.querySelectorAll('[data-workflow-volume-index], [data-workflow-chapter-index]').forEach((control) => {
    control.addEventListener('change', () => {
      updateWorkflowSelection({
        volumeIndex: Number(projectMini.querySelector('[data-workflow-volume-index]')?.value || currentSelection.volumeIndex || 1) || 1,
        chapterIndex: Number(projectMini.querySelector('[data-workflow-chapter-index]')?.value || currentSelection.chapterIndex || 1) || 1,
      });
    });
  });
}

function renderStageNav() {
  stageGroups.innerHTML = PAGE_STEP_GROUPS.workflow.map((group) => `
    <section class="nav-section">
      <div class="nav-section-head">
        <h3>${escapeHtml(group.label)}</h3>
      </div>
      <div class="nav-list">
        ${group.steps.map((step) => {
          const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks, selectionForStep(step));
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

function buildStepForm(step, selection) {
  const meta = getStepMeta(step);
  const project = currentSnapshot?.project;
  const fields = meta.fields || [];
  const primaryFields = fields.filter((field) => !field.advanced).map((field) => ({ ...field, stepKey: step }));
  const advancedFields = fields.filter((field) => field.advanced).map((field) => ({ ...field, stepKey: step }));
  const scopeKind = getStepScopeKind(step);
  const scopedArtifact = scopeKind === 'chapter' ? getScopedArtifact(currentSnapshot, step, selection) : getArtifact(currentSnapshot, step);

  return `
    <form class="workspace-form" data-step-form="${step}">
      <div class="form-grid">
        ${primaryFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, selection))).join('')}
      </div>
      ${advancedFields.length ? `
        <details class="advanced-panel">
          <summary>高级设置</summary>
          <div class="form-grid compact-grid">
            ${advancedFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, selection))).join('')}
          </div>
        </details>
      ` : ''}
      ${scopeKind === 'chapter' && step !== 'chapter' ? `
        <input type="hidden" name="volume_index" value="${selection.volumeIndex}" />
        <input type="hidden" name="chapter_index" value="${selection.chapterIndex}" />
      ` : ''}
      <div class="actions-row wrap">
        <button class="primary" type="submit" data-run-step="${step}">${isUnlocked(step, currentSnapshot, dependencyMap, selection) ? '执行当前对象' : '等待前置完成'}</button>
        <button class="ghost" type="button" data-delete-step="${step}" ${scopedArtifact ? '' : 'disabled'}>删除当前产物</button>
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
  const stepSelection = selectionForStep(step);
  const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks, stepSelection);
  workspaceTitle.textContent = `${meta.label} · ${meta.objectName}`;
  overview.innerHTML = renderStageOverview(VISIBLE_STEPS, currentSnapshot, dependencyMap, currentTasks, currentSelection);
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
          ${buildStepForm(step, stepSelection)}
        </div>
        <div>
          ${renderArtifactBlock(currentSnapshot, step, stepSelection)}
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

  form.querySelectorAll('[name="volume_index"], [name="chapter_index"]').forEach((control) => {
    control.addEventListener('change', () => {
      if (step !== 'chapter') {
        return;
      }
      updateWorkflowSelection({
        volumeIndex: Number(form.elements.namedItem('volume_index')?.value || currentSelection.volumeIndex || 1) || 1,
        chapterIndex: Number(form.elements.namedItem('chapter_index')?.value || currentSelection.chapterIndex || 1) || 1,
      });
    });
  });

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
        selection: stepSelection,
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
      const artifact = getStepScopeKind(step) === 'chapter' ? getScopedArtifact(currentSnapshot, step, stepSelection) : getArtifact(currentSnapshot, step);
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
  const stepSelection = selectionForStep(currentStep);
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
        ${renderDependencyList(currentStep, dependencyMap, currentSnapshot, currentSelection)}
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
  currentSelection = clampWorkflowSelection(snapshot, getWorkflowSelectionFromUrl());
  syncWorkflowSelectionToUrl(currentSelection);
  setSelectedProjectId(projectId);

  currentStep = VISIBLE_STEPS.includes(currentStep) ? currentStep : chooseDefaultStep();
  renderPage();
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
