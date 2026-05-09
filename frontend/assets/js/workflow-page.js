import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, PAGE_STEP_GROUPS, getStepLabel, getStepMeta, loadWorkflowContext } from './step-meta.js';
import { getArtifactForStep, getStepReadinessMessage, getStepStatus, getTasksForStepSelection, isUnlocked } from './artifact-selectors.js';
import { getChapterEntryOptions, getFieldDisplayValue, getSelectableChapterCount, getSelectableVolumeCount, getVolumeEntryOptions } from './planning-defaults.js';
import { badge, escapeHtml, formatDate, renderEmpty, renderNotice, summarizeList } from './dom.js';
import { getPageProjectId, getPreferredStep, setPreferredStep, setSelectedProjectId, syncProjectId, syncTopNavLinks, withProjectQuery } from './state.js';
import { deleteStepArtifact, hydrateChapterPlanDefaults, hydrateRoughChapterPlanDefaults, hydrateVolumeOutlineDefaults, renderArtifactBlock, renderChecklist, renderDependencyList, renderStageOverview, renderTaskList, renderField, runFieldCompletion, runStepFromForm } from './workspace-utils.js';
import { clampScopeSelection, getStepScopeKind, readScopeSelectionFromUrl, selectionForStep, syncScopeSelectionToUrl } from './scope-utils.js';

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
let currentSelection = readScopeSelectionFromUrl();

function updateWorkflowSelection(nextSelection) {
  currentSelection = clampScopeSelection(currentSnapshot, nextSelection, {
    getVolumeCount: getSelectableVolumeCount,
    getChapterCountForVolume: getSelectableChapterCount,
  });
  syncScopeSelectionToUrl(currentSelection);
  renderPage();
}

function renderSelectionOptions(options, selectedValue, emptyLabel) {
  if (!options.length) {
    return `<option value="">${escapeHtml(emptyLabel)}</option>`;
  }
  const selected = String(selectedValue || '');
  return options.map((option) => {
    const value = String(option.value || '');
    return `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(option.label || value)}</option>`;
  }).join('');
}

function renderSelectionCard(snapshot) {
  if (!snapshot) {
    return '';
  }

  const volumeOptions = getVolumeEntryOptions(snapshot);
  const chapterOptions = volumeOptions.length ? getChapterEntryOptions(snapshot, currentSelection.volumeIndex) : [];
  const hasVolumeOptions = volumeOptions.length > 0;
  const hasChapterOptions = chapterOptions.length > 0;
  const scopedArtifact = getArtifactForStep(snapshot, currentStep, selectionForStep(currentStep, currentSelection));
  const stepScopeKind = getStepScopeKind(currentStep);
  const scopedLabel = stepScopeKind === 'volume' ? '当前卷有对应产物' : stepScopeKind === 'chapter' ? '当前章节有对应产物' : '当前对象有对应产物';
  const scopeHint = stepScopeKind === 'volume' ? '当前步骤会按这个卷读写与删除。' : stepScopeKind === 'chapter' ? '当前步骤会按这个章节读写与删除。' : '切换到卷级或章节步骤后，会沿用这个上下文。';
  const emptyMessages = [
    hasVolumeOptions ? '' : '暂无可选卷条目，请先生成粗卷纲。',
    hasVolumeOptions && !hasChapterOptions ? '当前卷暂无可选章节条目，请先生成粗章纲。' : '',
  ].filter(Boolean);

  return `
    <div class="context-card subtle">
      <p class="eyebrow">章节上下文</p>
      <h3>第 ${currentSelection.volumeIndex} 卷 · 第 ${currentSelection.chapterIndex} 章</h3>
      <div class="form-grid">
        <div class="field">
          <label for="workflow-volume-index">卷序号</label>
          <select id="workflow-volume-index" data-workflow-volume-index ${hasVolumeOptions ? '' : 'disabled'}>
            ${renderSelectionOptions(volumeOptions, currentSelection.volumeIndex, '暂无可选卷条目')}
          </select>
        </div>
        <div class="field">
          <label for="workflow-chapter-index">章节条目</label>
          <select id="workflow-chapter-index" data-workflow-chapter-index ${hasChapterOptions ? '' : 'disabled'}>
            ${renderSelectionOptions(chapterOptions, currentSelection.chapterIndex, '暂无可选章节条目')}
          </select>
        </div>
      </div>
      <p class="muted">${scopeHint}</p>
      ${emptyMessages.map((message) => `<div class="notice warn">${escapeHtml(message)}</div>`).join('')}
      <div class="chips">
        ${badge(scopedArtifact ? scopedLabel : `${scopedLabel.replace('有对应产物', '暂无产物')}`, scopedArtifact ? 'success' : 'soft')}
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
  const unlocked = VISIBLE_STEPS.find((step) => isUnlocked(step, currentSnapshot, dependencyMap, selectionForStep(step, currentSelection)));
  return unlocked || VISIBLE_STEPS[0];
}

function buildNextAction(snapshot) {
  if (!snapshot) {
    return null;
  }
  for (const step of VISIBLE_STEPS) {
    const selection = selectionForStep(step, currentSelection);
    const status = getStepStatus(step, snapshot, dependencyMap, currentTasks, selection);
    if (status.text === '执行失败') {
      return {
        step,
        tone: 'danger',
        label: '先处理失败任务',
        detail: `${getStepLabel(step, workflowSteps)} 最近一次执行失败。`,
      };
    }
  }
  for (const step of VISIBLE_STEPS) {
    const selection = selectionForStep(step, currentSelection);
    if (!getArtifactForStep(snapshot, step, selection) && isUnlocked(step, snapshot, dependencyMap, selection)) {
      return {
        step,
        tone: step === 'chapter' ? 'accent' : 'warn',
        label: step === currentStep ? '当前对象可执行' : `建议处理：${getStepLabel(step, workflowSteps)}`,
        detail: getStepMeta(step).objectName || getStepMeta(step).label || step,
      };
    }
  }
  return {
    step: 'consistency',
    tone: 'success',
    label: '当前上下文链路完整',
    detail: '可以进入审查台查看质量报告或导出成稿。',
  };
}

function renderNextAction(snapshot) {
  const action = buildNextAction(snapshot);
  if (!action) {
    return '';
  }
  const scopeKind = getStepScopeKind(action.step);
  const scopeText = scopeKind === 'chapter'
    ? `第 ${currentSelection.volumeIndex} 卷 · 第 ${currentSelection.chapterIndex} 章`
    : scopeKind === 'volume'
      ? `第 ${currentSelection.volumeIndex} 卷`
      : '全书';
  return `
    <div class="context-card subtle">
      <div class="context-head">
        <div>
          <p class="eyebrow">建议下一步</p>
          <h3>${escapeHtml(action.label)}</h3>
        </div>
        ${badge(scopeText, action.tone)}
      </div>
      <p class="muted">${escapeHtml(action.detail)}</p>
      <div class="actions-row wrap">
        <button type="button" class="secondary" data-jump-next-step="${escapeHtml(action.step)}">打开对象</button>
        <a class="secondary-link" href="${withProjectQuery('/review', snapshot.project.project_id)}">审查台</a>
      </div>
    </div>
  `;
}

function renderPhaseRail(snapshot) {
  const groups = PAGE_STEP_GROUPS.workflow;
  return `
    <div class="phase-rail" aria-label="工作流阶段">
      ${groups.map((group) => {
        const done = group.steps.filter((step) => getArtifactForStep(snapshot, step, selectionForStep(step, currentSelection))).length;
        const total = group.steps.length || 1;
        const active = group.steps.includes(currentStep);
        const percent = Math.round((done / total) * 100);
        return `
          <button type="button" class="phase-step ${active ? 'active' : ''}" data-phase-step="${escapeHtml(group.steps[0])}">
            <span>${escapeHtml(group.label)}</span>
            <strong>${done}/${total}</strong>
            <i><b style="width:${percent}%"></b></i>
          </button>
        `;
      }).join('')}
    </div>
  `;
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
    ${renderPhaseRail(snapshot)}
    ${renderNextAction(snapshot)}
    ${renderSelectionCard(snapshot)}
  `;

  projectMini.querySelectorAll('[data-jump-next-step], [data-phase-step]').forEach((button) => {
    button.addEventListener('click', (event) => {
      const step = event.currentTarget.getAttribute('data-jump-next-step') || event.currentTarget.getAttribute('data-phase-step');
      if (!step) {
        return;
      }
      currentStep = step;
      setPreferredStep(PAGE_KEY, step);
      renderPage();
    });
  });

  projectMini.querySelectorAll('[data-workflow-volume-index], [data-workflow-chapter-index]').forEach((control) => {
    control.addEventListener('change', () => {
      const volumeChanged = control.matches('[data-workflow-volume-index]');
      updateWorkflowSelection({
        volumeIndex: Number(projectMini.querySelector('[data-workflow-volume-index]')?.value || currentSelection.volumeIndex || 1) || 1,
        chapterIndex: volumeChanged ? 1 : Number(projectMini.querySelector('[data-workflow-chapter-index]')?.value || currentSelection.chapterIndex || 1) || 1,
      });
    });
  });
}

function renderStepBrief(step, selection) {
  const meta = getStepMeta(step);
  const dependencies = dependencyMap[step] || [];
  const dependents = workflowSteps.filter((item) => (item.depends_on || []).includes(step)).map((item) => item.key);
  const scopeKind = getStepScopeKind(step);
  const scopeText = scopeKind === 'chapter'
    ? `第 ${selection.volumeIndex} 卷 · 第 ${selection.chapterIndex} 章`
    : scopeKind === 'volume'
      ? `第 ${selection.volumeIndex} 卷`
      : '全书';
  const inputText = dependencies.length ? dependencies.map((dep) => getStepLabel(dep, workflowSteps)).join('、') : '项目基础设定';
  const outputText = meta.objectName || meta.label || step;
  const nextText = dependents.length ? dependents.map((dep) => getStepLabel(dep, workflowSteps)).join('、') : '审查与导出';
  return `
    <div class="step-brief">
      <div><span>读取</span><strong>${escapeHtml(inputText)}</strong></div>
      <div><span>产出</span><strong>${escapeHtml(outputText)}</strong></div>
      <div><span>范围</span><strong>${escapeHtml(scopeText)}</strong></div>
      <div><span>影响</span><strong>${escapeHtml(nextText)}</strong></div>
    </div>
  `;
}

function runButtonText(step, artifact, unlocked) {
  if (!unlocked) {
    return '等待前置完成';
  }
  const name = getStepMeta(step).objectName || getStepLabel(step, workflowSteps);
  return `${artifact ? '重新生成' : '生成'}${name}`;
}

function renderStageNav() {
  stageGroups.innerHTML = PAGE_STEP_GROUPS.workflow.map((group) => `
    <section class="nav-section">
      <div class="nav-section-head">
        <h3>${escapeHtml(group.label)}</h3>
      </div>
      <div class="nav-list">
        ${group.steps.map((step) => {
          const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks, selectionForStep(step, currentSelection));
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
  const fieldKeys = new Set(fields.map((field) => field.key));
  const primaryFields = fields.filter((field) => !field.advanced).map((field) => ({ ...field, stepKey: step }));
  const advancedFields = fields.filter((field) => field.advanced).map((field) => ({ ...field, stepKey: step }));
  const scopeKind = getStepScopeKind(step);
  const scopedArtifact = getArtifactForStep(currentSnapshot, step, selectionForStep(step, selection));
  const unlocked = isUnlocked(step, currentSnapshot, dependencyMap, selection);
  const readinessMessage = getStepReadinessMessage(step, currentSnapshot, dependencyMap, selection);
  const fieldContext = { project, snapshot: currentSnapshot, selection };
  const hiddenScopeInputs = [
    scopeKind !== 'project' && !fieldKeys.has('volume_index') ? `<input type="hidden" name="volume_index" value="${selection.volumeIndex}" />` : '',
    scopeKind === 'chapter' && !fieldKeys.has('chapter_index') ? `<input type="hidden" name="chapter_index" value="${selection.chapterIndex}" />` : '',
  ].join('');

  return `
    <form class="workspace-form" data-step-form="${step}">
      <div class="form-grid">
        ${primaryFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, selection), fieldContext)).join('')}
      </div>
      ${advancedFields.length ? `
        <details class="advanced-panel">
          <summary>高级设置</summary>
          <div class="form-grid compact-grid">
            ${advancedFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, selection), fieldContext)).join('')}
          </div>
        </details>
      ` : ''}
      ${hiddenScopeInputs}
      <div class="actions-row wrap">
        <button class="primary" type="submit" data-run-step="${step}" ${unlocked ? '' : 'disabled'} title="${escapeHtml(readinessMessage)}">${escapeHtml(runButtonText(step, scopedArtifact, unlocked))}</button>
        <button class="ghost" type="button" data-delete-step="${step}" ${scopedArtifact ? '' : 'disabled'}>删除当前产物</button>
        <span class="muted">删除会级联清理依赖此对象的下游内容。</span>
      </div>
      ${unlocked ? '' : `<div class="notice warn">${escapeHtml(readinessMessage)}</div>`}
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
  const stepSelection = selectionForStep(step, currentSelection);
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
      ${renderStepBrief(step, stepSelection)}
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
  if (step === 'rough_chapter_plan') {
    hydrateRoughChapterPlanDefaults(form, currentSnapshot);
  }
  if (step === 'chapter_plan') {
    hydrateChapterPlanDefaults(form, currentSnapshot);
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
    if (!isUnlocked(step, currentSnapshot, dependencyMap, stepSelection)) {
      messageBox.hidden = false;
      messageBox.className = 'notice error';
      messageBox.textContent = getStepReadinessMessage(step, currentSnapshot, dependencyMap, stepSelection) || '前置对象还没准备好，请先完成依赖步骤。';
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
      const artifact = getArtifactForStep(currentSnapshot, step, stepSelection);
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
  const stepSelection = selectionForStep(currentStep, currentSelection);
  const stepTasks = getTasksForStepSelection(currentStep, currentTasks, stepSelection);
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
        ${renderDependencyList(currentStep, dependencyMap, currentSnapshot, stepSelection)}
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
  currentSelection = clampScopeSelection(snapshot, readScopeSelectionFromUrl(), {
    getVolumeCount: getSelectableVolumeCount,
    getChapterCountForVolume: getSelectableChapterCount,
  });
  syncScopeSelectionToUrl(currentSelection);
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
