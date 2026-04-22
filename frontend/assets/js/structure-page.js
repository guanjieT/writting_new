import { api } from './api-client.js';
import { FALLBACK_WORKFLOW_STEPS, getStepLabel, getStepMeta, loadWorkflowContext } from './step-meta.js';
import { getArtifactForStep, getStepReadinessMessage, getStepStatus, getTasksForSelection, isUnlocked } from './artifact-selectors.js';
import { getChapterEntryOptions, getFieldDisplayValue, getSelectableChapterCount, getSelectableVolumeCount, getVolumeEntryOptions } from './planning-defaults.js';
import { badge, escapeHtml, renderEmpty, renderNotice, summarizeList } from './dom.js';
import { getPageProjectId, syncProjectId, syncTopNavLinks } from './state.js';
import { deleteStepArtifact, hydrateChapterPlanDefaults, hydrateRoughChapterPlanDefaults, hydrateVolumeOutlineDefaults, renderArtifactBlock, renderDependencyList, renderField, renderStageOverview, renderTaskList, runFieldCompletion, runStepFromForm } from './workspace-utils.js';
import { clampScopeSelection, readScopeSelectionFromUrl, selectionForStep, syncScopeSelectionToUrl } from './scope-utils.js';

const PAGE_KEY = document.body.dataset.page || 'outline';
const PAGE_CONFIG = {
  outline: {
    title: '结构台',
    eyebrow: '总纲页面',
    description: '只展示总纲与全书粗卷纲。',
    steps: ['outline', 'rough_volume_outline'],
  },
  'volume-outline': {
    title: '卷纲页面',
    eyebrow: '卷纲页面',
    description: '只展示当前卷的完善卷纲与粗章纲。',
    steps: ['volume_outline', 'rough_chapter_plan'],
  },
  'chapter-plan': {
    title: '章节计划页面',
    eyebrow: '章节计划页面',
    description: '只展示当前章的完善章节计划。',
    steps: ['chapter_plan'],
  },
};

const PAGE = PAGE_CONFIG[PAGE_KEY] || PAGE_CONFIG.outline;
const projectMini = document.getElementById('structure-project-mini');
const selectionPanel = document.getElementById('structure-selection');
const overview = document.getElementById('structure-overview');
const workspace = document.getElementById('structure-workspace');
const inspector = document.getElementById('structure-inspector');
const reloadButton = document.getElementById('reload-structure');
const pageTitle = document.getElementById('structure-workspace-title');
const pageSubtitle = document.getElementById('structure-workspace-subtitle');

let dependencyMap = Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []]));
let currentSnapshot = null;
let currentTasks = [];

function reloadWithSelection(nextSelection) {
  syncScopeSelectionToUrl(nextSelection);
  return loadPage();
}

function buildSelectionUrl(path, projectId, selection) {
  const url = new URL(path, window.location.origin);
  if (projectId) {
    url.searchParams.set('project_id', projectId);
  }
  if (selection?.volumeIndex) {
    url.searchParams.set('volume_index', String(selection.volumeIndex));
  }
  if (selection?.chapterIndex) {
    url.searchParams.set('chapter_index', String(selection.chapterIndex));
  }
  return `${url.pathname}${url.search}`;
}

function renderProjectMini(snapshot, selection) {
  if (!snapshot) {
    renderEmpty(projectMini, '请先在项目台选择一个项目。');
    return;
  }
  const project = snapshot.project;
  const chips = [
    `${project.input.target_volume_count} 卷`,
    `${project.input.target_chapters_per_volume} 章/卷`,
    `${project.input.target_words} 字`,
  ];
  if (PAGE_KEY !== 'outline') {
    chips.unshift(`当前卷 ${selection.volumeIndex}`);
  }
  if (PAGE_KEY === 'chapter-plan') {
    chips.unshift(`当前章 ${selection.chapterIndex}`);
  }

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
        ${chips.map((item) => badge(item, 'soft')).join('')}
      </div>
      <p class="muted">总纲关注：${escapeHtml(summarizeList(project.input.outline_focus))}</p>
    </div>
  `;
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

function renderSelection(snapshot, selection) {
  if (!selectionPanel) {
    return;
  }

  const project = snapshot?.project;
  const volumeOptions = getVolumeEntryOptions(snapshot);
  const chapterOptions = volumeOptions.length ? getChapterEntryOptions(snapshot, selection.volumeIndex) : [];
  const hasVolumeOptions = volumeOptions.length > 0;
  const hasChapterOptions = chapterOptions.length > 0;

  selectionPanel.innerHTML = PAGE_KEY === 'outline' ? `
    <div class="context-card subtle">
      <p class="eyebrow">页面说明</p>
      <h3>总纲与粗卷纲</h3>
      <p class="muted">这里只展示总纲和全书粗卷纲。粗卷纲按钮会一次生成全书所有卷，不按卷拆分。</p>
      <div class="actions-row wrap">
        <a class="secondary-link" href="${buildSelectionUrl('/volume-outline', project?.project_id || '', { volumeIndex: 1, chapterIndex: 1 })}">去卷纲页面</a>
        <a class="secondary-link" href="${buildSelectionUrl('/chapter-plan', project?.project_id || '', { volumeIndex: 1, chapterIndex: 1 })}">去章节计划页面</a>
      </div>
    </div>
  ` : PAGE_KEY === 'volume-outline' ? `
    <div class="context-card subtle">
      <p class="eyebrow">卷选择</p>
      <h3>当前第 ${selection.volumeIndex} 卷</h3>
      <div class="field full">
        <label for="volume-index-select">卷序号</label>
        <select id="volume-index-select" name="volume_index" ${hasVolumeOptions ? '' : 'disabled'}>
          ${renderSelectionOptions(volumeOptions, selection.volumeIndex, '暂无可选卷条目')}
        </select>
      </div>
      <p class="muted">${hasVolumeOptions ? '卷纲和粗章纲都只处理当前卷。' : '暂无可选卷条目，请先在总纲页面生成粗卷纲。'}</p>
      <div class="actions-row wrap">
        <a class="secondary-link" href="${buildSelectionUrl('/outline', project?.project_id || '', { volumeIndex: 1, chapterIndex: 1 })}">去总纲页面</a>
        <a class="secondary-link" href="${buildSelectionUrl('/chapter-plan', project?.project_id || '', selection)}">去章节计划页面</a>
      </div>
    </div>
  ` : `
    <div class="context-card subtle">
      <p class="eyebrow">卷章选择</p>
      <h3>当前第 ${selection.volumeIndex} 卷 · 第 ${selection.chapterIndex} 章</h3>
      <div class="form-grid">
        <div class="field">
          <label for="volume-index-select">卷序号</label>
          <select id="volume-index-select" name="volume_index" ${hasVolumeOptions ? '' : 'disabled'}>
            ${renderSelectionOptions(volumeOptions, selection.volumeIndex, '暂无可选卷条目')}
          </select>
        </div>
        <div class="field">
          <label for="chapter-index-select">章节条目</label>
          <select id="chapter-index-select" name="chapter_index" ${hasChapterOptions ? '' : 'disabled'}>
            ${renderSelectionOptions(chapterOptions, selection.chapterIndex, '暂无可选章节条目')}
          </select>
        </div>
      </div>
      <p class="muted">${!hasVolumeOptions ? '暂无可选卷条目，请先在总纲页面生成粗卷纲。' : hasChapterOptions ? '章节计划只处理当前章，按钮会依赖当前卷的粗章纲条目。' : '当前卷暂无可选章节条目，请先在卷纲页面生成粗章纲。'}</p>
      <div class="actions-row wrap">
        <a class="secondary-link" href="${buildSelectionUrl('/outline', project?.project_id || '', selection)}">去总纲页面</a>
        <a class="secondary-link" href="${buildSelectionUrl('/volume-outline', project?.project_id || '', selection)}">去卷纲页面</a>
      </div>
    </div>
  `;

  selectionPanel.querySelectorAll('select').forEach((control) => {
    control.addEventListener('change', () => {
      const volumeChanged = control.getAttribute('name') === 'volume_index';
      const nextSelection = { ...selection };
      nextSelection.volumeIndex = Number(selectionPanel.querySelector('[name="volume_index"]')?.value || selection.volumeIndex || 1);
      nextSelection.chapterIndex = volumeChanged ? 1 : Number(selectionPanel.querySelector('[name="chapter_index"]')?.value || selection.chapterIndex || 1);
      reloadWithSelection(nextSelection).catch((error) => renderNotice(workspace, error.message, 'error'));
    });
  });
}

function actionLabel(step, artifact) {
  const labels = {
    outline: '生成总纲',
    rough_volume_outline: '生成粗卷纲',
    volume_outline: '完善本卷卷纲',
    rough_chapter_plan: '生成本卷粗章纲',
    chapter_plan: '完善本章章节计划',
  };
  const base = labels[step] || getStepMeta(step).label || '执行';
  return artifact ? `重新${base}` : base;
}

function renderStepCard(step, selection) {
  const project = currentSnapshot?.project;
  const meta = getStepMeta(step);
  const stepSelection = selectionForStep(step, selection);
  const status = getStepStatus(step, currentSnapshot, dependencyMap, currentTasks, stepSelection);
  const artifact = getArtifactForStep(currentSnapshot, step, stepSelection);
  const unlocked = isUnlocked(step, currentSnapshot, dependencyMap, stepSelection);
  const readinessMessage = getStepReadinessMessage(step, currentSnapshot, dependencyMap, stepSelection);
  const fields = (meta.fields || []).map((field) => ({ ...field, stepKey: step }));
  const primaryFields = fields.filter((field) => !field.advanced);
  const advancedFields = fields.filter((field) => field.advanced);
  const fieldContext = { project, snapshot: currentSnapshot, selection: stepSelection };

  return `
    <section class="workspace-card">
      <div class="workspace-card-head">
        <div>
          <p class="eyebrow">${escapeHtml(PAGE.eyebrow)}</p>
          <h3>${escapeHtml(meta.objectName || meta.label)}</h3>
          <p class="muted">${escapeHtml(meta.description || '')}</p>
        </div>
        ${badge(status.text, status.tone)}
      </div>
      <div class="workspace-card-grid">
        <div>
          <form class="workspace-form" data-step-form="${step}">
            <div class="form-grid">
              ${primaryFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, stepSelection), fieldContext)).join('')}
            </div>
            ${advancedFields.length ? `
              <details class="advanced-panel">
                <summary>高级设置</summary>
                <div class="form-grid compact-grid">
                  ${advancedFields.map((field) => renderField(field, getFieldDisplayValue(field, project, currentSnapshot, stepSelection), fieldContext)).join('')}
                </div>
              </details>
            ` : ''}
            <div class="actions-row wrap">
              <button class="primary" type="submit" ${unlocked ? '' : 'disabled'} title="${escapeHtml(readinessMessage)}">${unlocked ? actionLabel(step, artifact) : '等待前置完成'}</button>
              <button class="ghost" type="button" data-delete-step="${step}" ${artifact ? '' : 'disabled'}>删除当前产物</button>
            </div>
            ${unlocked ? '' : `<div class="notice warn">${escapeHtml(readinessMessage)}</div>`}
            <div class="notice info" data-step-message hidden></div>
          </form>
        </div>
        <div>${renderArtifactBlock(currentSnapshot, step, stepSelection)}</div>
      </div>
    </section>
  `;
}

function renderWorkspace(selection) {
  const steps = PAGE.steps;
  pageTitle.textContent = PAGE.title;
  pageSubtitle.textContent = PAGE.description;
  overview.innerHTML = renderStageOverview(steps, currentSnapshot, dependencyMap, currentTasks, PAGE_KEY === 'outline' ? {} : selectionForStep(steps[0], selection));
  workspace.innerHTML = steps.map((step) => renderStepCard(step, selection)).join('');

  workspace.querySelectorAll('[data-step-form]').forEach((form) => {
    const step = form.getAttribute('data-step-form');
    const messageBox = form.querySelector('[data-step-message]');
    const deleteButton = form.querySelector('[data-delete-step]');
    const stepSelection = step === 'volume_outline' || step === 'rough_chapter_plan' ? { volumeIndex: selection.volumeIndex } : step === 'chapter_plan' ? selection : {};
    const stepMeta = getStepMeta(step);

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
      }
    });

    deleteButton.addEventListener('click', async () => {
      try {
        const artifact = getArtifactForStep(currentSnapshot, step, stepSelection);
        const result = await deleteStepArtifact({
          projectId: currentSnapshot.project.project_id,
          artifactKey: artifact?.key,
          label: stepMeta.objectName || stepMeta.label,
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
  });

  inspector.innerHTML = `
    <div class="stack-list">
      <section class="context-card">
        <p class="eyebrow">页面范围</p>
        <h3>${escapeHtml(PAGE.title)}</h3>
        <p class="muted">${escapeHtml(PAGE.description)}</p>
      </section>

      <section class="context-card">
        <p class="eyebrow">依赖检查</p>
        <h3>${escapeHtml(PAGE.steps.map((step) => getStepLabel(step)).join(' / '))}</h3>
        ${renderDependencyList(PAGE.steps[0], dependencyMap, currentSnapshot, PAGE_KEY === 'outline' ? {} : selectionForStep(PAGE.steps[0], selection))}
      </section>

      <section class="context-card">
        <p class="eyebrow">最近任务</p>
        <h3>结构执行记录</h3>
        ${renderTaskList(getTasksForSelection(currentTasks, PAGE.steps, PAGE_KEY === 'outline' ? {} : selection), { limit: 6 })}
      </section>

      <section class="context-card subtle">
        <p class="eyebrow">联动入口</p>
        <h3>跨页面跳转</h3>
        <div class="actions-row wrap">
          <a class="secondary-link" href="${buildSelectionUrl('/outline', currentSnapshot.project.project_id, selection)}">总纲页面</a>
          <a class="secondary-link" href="${buildSelectionUrl('/volume-outline', currentSnapshot.project.project_id, selection)}">卷纲页面</a>
          <a class="secondary-link" href="${buildSelectionUrl('/chapter-plan', currentSnapshot.project.project_id, selection)}">章节计划页面</a>
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
    selectionPanel.innerHTML = '';
    return;
  }

  syncProjectId(projectId);
  syncTopNavLinks(projectId);
  const [context, snapshot, tasks] = await Promise.all([
    loadWorkflowContext(),
    api.getProjectSnapshot(projectId),
    api.listTasks(projectId),
  ]);

  dependencyMap = context.dependencies || dependencyMap;
  currentSnapshot = snapshot;
  currentTasks = tasks;

  const selection = clampScopeSelection(snapshot, readScopeSelectionFromUrl(), {
    getVolumeCount: getSelectableVolumeCount,
    getChapterCountForVolume: getSelectableChapterCount,
  });
  syncScopeSelectionToUrl(selection);
  renderProjectMini(snapshot, selection);
  renderSelection(snapshot, selection);
  renderWorkspace(selection);
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
