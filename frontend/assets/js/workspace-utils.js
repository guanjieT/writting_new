import { api } from './api-client.js';
import { waitForTask } from './api-client.js';
import { badge, escapeHtml, formatDate, renderJsonPreview, truncate } from './dom.js';
import { getArtifact, getArtifactForStep, getScopedArtifact, getStepStatus } from './artifact-selectors.js';
import { getStepDependencies, getStepLabel, getStepMeta } from './step-meta.js';
import { extractChapterPlanDefaults, extractVolumeOutlineDefaults } from './planning-defaults.js';
import { dependencySelectionFor, normalizeScopeSelection } from './scope-utils.js';
import { listFromText } from './state.js';

export function renderField(field, value) {
  const safeValue = value ?? '';
  const isTextarea = field.type === 'textarea';
  const isCompletable = field.type !== 'checkbox';
  const isFull = field.full !== undefined ? field.full : isTextarea || Boolean(field.list);
  const inputId = `${field.stepKey || 'step'}-${field.key}`;

  if (field.type === 'checkbox') {
    return `
      <label class="field checkbox-field">
        <span>${escapeHtml(field.label)}</span>
        <input id="${escapeHtml(inputId)}" type="checkbox" name="${field.key}" ${safeValue ? 'checked' : ''} />
      </label>
    `;
  }

  if (isTextarea) {
    return `
      <div class="field ${isFull ? 'full' : ''}">
        <div class="field-head">
          <label for="${escapeHtml(inputId)}">${escapeHtml(field.label)}</label>
          ${isCompletable ? `<button type="button" class="field-ai" data-ai-complete data-field-key="${escapeHtml(field.key)}" data-field-label="${escapeHtml(field.label)}" data-field-type="${escapeHtml(field.type)}" data-field-placeholder="${escapeHtml(field.placeholder || '')}">AI 补全</button>` : ''}
        </div>
        <textarea id="${escapeHtml(inputId)}" name="${field.key}" rows="${field.rows || 4}" placeholder="${escapeHtml(field.placeholder || '')}">${escapeHtml(safeValue)}</textarea>
      </div>
    `;
  }

  return `
    <div class="field ${isFull ? 'full' : ''}">
      <div class="field-head">
        <label for="${escapeHtml(inputId)}">${escapeHtml(field.label)}</label>
        ${isCompletable ? `<button type="button" class="field-ai" data-ai-complete data-field-key="${escapeHtml(field.key)}" data-field-label="${escapeHtml(field.label)}" data-field-type="${escapeHtml(field.type)}" data-field-placeholder="${escapeHtml(field.placeholder || '')}">AI 补全</button>` : ''}
      </div>
      <input id="${escapeHtml(inputId)}" name="${field.key}" type="${field.type}" value="${escapeHtml(String(safeValue))}" ${field.step ? `step="${field.step}"` : ''} placeholder="${escapeHtml(field.placeholder || '')}" />
    </div>
  `;
}

export function hydrateVolumeOutlineDefaults(form, snapshot) {
  if (!form) {
    return;
  }

  const volumeIndexField = form.elements.namedItem('volume_index');
  const selectedVolumeIndex = Number(volumeIndexField?.value || 1) || 1;
  const defaults = extractVolumeOutlineDefaults(snapshot, selectedVolumeIndex);
  if (!defaults) {
    return;
  }

  const assignValue = (fieldName, nextValue) => {
    const control = form.elements.namedItem(fieldName);
    if (!control) {
      return;
    }
    const sourceIndex = String(selectedVolumeIndex);
    const shouldOverwrite = !String(control.value || '').trim() || control.dataset.volumeOutlineSourceIndex !== sourceIndex;
    if (control.type === 'checkbox') {
      if (shouldOverwrite) {
        control.checked = Boolean(nextValue);
        control.dataset.volumeOutlineSourceIndex = sourceIndex;
      }
      return;
    }
    if (control.tagName === 'TEXTAREA' && Array.isArray(nextValue)) {
      if (shouldOverwrite) {
        control.value = nextValue.join('\n');
        control.dataset.volumeOutlineSourceIndex = sourceIndex;
      }
      return;
    }
    if (!shouldOverwrite) {
      return;
    }
    control.value = Array.isArray(nextValue) ? nextValue.join('\n') : String(nextValue ?? '');
    control.dataset.volumeOutlineSourceIndex = sourceIndex;
  };

  assignValue('volume_title', defaults.volume_title);
  assignValue('volume_summary', defaults.volume_summary);
  assignValue('volume_goal', defaults.volume_goal);
  assignValue('volume_conflict', defaults.volume_conflict);
  assignValue('volume_hook', defaults.volume_hook);
  assignValue('chapter_briefs', defaults.chapter_briefs);

  const targetChapterCountField = form.elements.namedItem('target_chapter_count');
  if (targetChapterCountField) {
    const sourceIndex = String(selectedVolumeIndex);
    const shouldOverwrite = !String(targetChapterCountField.value || '').trim() || targetChapterCountField.dataset.volumeOutlineSourceIndex !== sourceIndex;
    if (shouldOverwrite && defaults.target_chapter_count) {
      targetChapterCountField.value = String(defaults.target_chapter_count);
      targetChapterCountField.dataset.volumeOutlineSourceIndex = sourceIndex;
    }
  }

  if (volumeIndexField && !volumeIndexField.dataset.volumeOutlineHydrateBound) {
    volumeIndexField.addEventListener('input', () => hydrateVolumeOutlineDefaults(form, snapshot));
    volumeIndexField.addEventListener('change', () => hydrateVolumeOutlineDefaults(form, snapshot));
    volumeIndexField.dataset.volumeOutlineHydrateBound = 'true';
  }
}

export function hydrateChapterPlanDefaults(form, snapshot) {
  if (!form) {
    return;
  }

  const volumeIndexField = form.elements.namedItem('volume_index');
  const chapterIndexField = form.elements.namedItem('chapter_index');
  const selectedVolumeIndex = Number(volumeIndexField?.value || 1) || 1;
  const selectedChapterIndex = Number(chapterIndexField?.value || 1) || 1;
  const defaults = extractChapterPlanDefaults(snapshot, selectedVolumeIndex, selectedChapterIndex);
  if (!defaults) {
    return;
  }

  const assignValue = (fieldName, nextValue) => {
    const control = form.elements.namedItem(fieldName);
    if (!control) {
      return;
    }
    const sourceKey = `${selectedVolumeIndex}:${selectedChapterIndex}`;
    const shouldOverwrite = !String(control.value || '').trim() || control.dataset.chapterPlanSourceKey !== sourceKey;
    if (control.type === 'checkbox') {
      if (shouldOverwrite) {
        control.checked = Boolean(nextValue);
        control.dataset.chapterPlanSourceKey = sourceKey;
      }
      return;
    }
    if (control.tagName === 'TEXTAREA' && Array.isArray(nextValue)) {
      if (shouldOverwrite) {
        control.value = nextValue.join('\n');
        control.dataset.chapterPlanSourceKey = sourceKey;
      }
      return;
    }
    if (!shouldOverwrite) {
      return;
    }
    control.value = Array.isArray(nextValue) ? nextValue.join('\n') : String(nextValue ?? '');
    control.dataset.chapterPlanSourceKey = sourceKey;
  };

  assignValue('chapter_title', defaults.chapter_title);
  assignValue('chapter_summary', defaults.chapter_summary);
  assignValue('chapter_type', defaults.chapter_type);
  assignValue('pov_character', defaults.pov_character);
  assignValue('conflict', defaults.conflict);
  assignValue('hook', defaults.hook);
  assignValue('scene_summaries', defaults.scene_summaries);

  if (volumeIndexField && !volumeIndexField.dataset.chapterPlanHydrateBound) {
    volumeIndexField.addEventListener('input', () => hydrateChapterPlanDefaults(form, snapshot));
    volumeIndexField.addEventListener('change', () => hydrateChapterPlanDefaults(form, snapshot));
    volumeIndexField.dataset.chapterPlanHydrateBound = 'true';
  }

  if (chapterIndexField && !chapterIndexField.dataset.chapterPlanHydrateBound) {
    chapterIndexField.addEventListener('input', () => hydrateChapterPlanDefaults(form, snapshot));
    chapterIndexField.addEventListener('change', () => hydrateChapterPlanDefaults(form, snapshot));
    chapterIndexField.dataset.chapterPlanHydrateBound = 'true';
  }
}

export function hydrateRoughChapterPlanDefaults(form, snapshot) {
  if (!form) {
    return;
  }

  const volumeIndexField = form.elements.namedItem('volume_index');
  const selectedVolumeIndex = Number(volumeIndexField?.value || 1) || 1;
  const defaults = extractVolumeOutlineDefaults(snapshot, selectedVolumeIndex);
  if (!defaults) {
    return;
  }

  const targetChapterCountField = form.elements.namedItem('target_chapter_count');
  if (targetChapterCountField) {
    const sourceIndex = String(selectedVolumeIndex);
    const shouldOverwrite = !String(targetChapterCountField.value || '').trim() || targetChapterCountField.dataset.roughChapterPlanSourceIndex !== sourceIndex;
    if (shouldOverwrite && defaults.target_chapter_count) {
      targetChapterCountField.value = String(defaults.target_chapter_count);
      targetChapterCountField.dataset.roughChapterPlanSourceIndex = sourceIndex;
    }
  }

  if (volumeIndexField && !volumeIndexField.dataset.roughChapterPlanHydrateBound) {
    volumeIndexField.addEventListener('input', () => hydrateRoughChapterPlanDefaults(form, snapshot));
    volumeIndexField.addEventListener('change', () => hydrateRoughChapterPlanDefaults(form, snapshot));
    volumeIndexField.dataset.roughChapterPlanHydrateBound = 'true';
  }
}

export async function runFieldCompletion({ projectId, step, form, button, onProgress }) {
  const fieldKey = button.getAttribute('data-field-key');
  const fieldLabel = button.getAttribute('data-field-label') || fieldKey || '';
  const fieldType = button.getAttribute('data-field-type') || 'text';
  const field = fieldKey ? form.elements.namedItem(fieldKey) : null;

  if (!field) {
    throw new Error('找不到对应字段。');
  }

  const payload = serializeStepPayload(form, step);
  const currentValue = fieldType === 'checkbox' ? Boolean(field.checked) : String(field.value || '');

  onProgress?.(`正在补全“${fieldLabel}”...`);
  const result = await api.completeField(projectId, {
    step,
    step_label: getStepLabel(step),
    step_description: getStepMeta(step).description || '',
    field_key: fieldKey,
    field_label: fieldLabel,
    field_type: fieldType,
    field_placeholder: button.getAttribute('data-field-placeholder') || '',
    current_value: String(currentValue),
    payload,
    temperature: Number(payload.temperature || 0.7),
    max_tokens: Number(payload.max_tokens || 700),
  });

  const suggestion = String(result?.suggestion || '').trim();
  if (fieldType === 'checkbox') {
    field.checked = suggestion.toLowerCase() === 'true';
  } else if (field.type === 'number') {
    const parsed = Number.parseFloat(suggestion.replace(/[^0-9.+-]/g, ''));
    field.value = Number.isFinite(parsed) ? String(parsed) : suggestion;
  } else {
    field.value = suggestion;
  }

  field.dispatchEvent(new Event('input', { bubbles: true }));
  field.dispatchEvent(new Event('change', { bubbles: true }));
  onProgress?.('AI 补全已回填。');
}

function serializeStepPayload(form, step) {
  const fields = getStepMeta(step).fields || [];
  const formData = new FormData(form);
  const payload = {};
  for (const field of fields) {
    const rawValue = formData.get(field.key);
    if (field.type === 'checkbox') {
      payload[field.key] = rawValue === 'on';
      continue;
    }
    if (field.type === 'number') {
      payload[field.key] = Number(rawValue || field.defaultValue || 0);
      continue;
    }
    if (field.list) {
      payload[field.key] = listFromText(rawValue || '');
      continue;
    }
    payload[field.key] = String(rawValue || '').trim();
  }
  return payload;
}

export function renderArtifactBlock(snapshot, step, selection = {}) {
  const artifact = getArtifactForStep(snapshot, step, selection);
  const meta = getStepMeta(step);
  if (!artifact) {
    return `
      <section class="artifact-viewer empty-surface">
        <p class="eyebrow">当前产物</p>
        <h3>${escapeHtml(meta.objectName || meta.label)}</h3>
        <p class="muted">这个对象还没有产出结果。先补齐输入，再执行生成。</p>
      </section>
    `;
  }

  const summary = artifact.summary || {};
  const bestForSteps = Array.isArray(summary.best_for_steps) ? summary.best_for_steps : [];
  const renderList = (items) => items.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<p class="muted">暂无</p>';

  return `
    <section class="artifact-viewer">
      <div class="artifact-head">
        <div>
          <p class="eyebrow">当前产物</p>
          <h3>${escapeHtml(artifact.title || meta.objectName || meta.label)}</h3>
        </div>
        ${badge('已产出', 'success')}
      </div>
      <section class="artifact-summary">
        <p class="eyebrow">结构化摘要</p>
        <p class="muted">${escapeHtml(summary.summary || summary.overview || '暂无摘要。')}</p>
        <details>
          <summary>关键事实</summary>
          ${renderList(Array.isArray(summary.key_facts) ? summary.key_facts : [])}
        </details>
        <details>
          <summary>约束与禁忌</summary>
          ${renderList(Array.isArray(summary.constraints) ? summary.constraints : [])}
        </details>
        <details>
          <summary>未决问题</summary>
          ${renderList(Array.isArray(summary.open_questions) ? summary.open_questions : [])}
        </details>
        <details>
          <summary>适用步骤</summary>
          <p class="muted">${escapeHtml(bestForSteps.map((item) => getStepLabel(item)).join('、') || '暂无')}</p>
        </details>
      </section>
      <p class="muted">${escapeHtml(truncate(artifact.content, 120))}</p>
      <details open>
        <summary>展开查看正文</summary>
        <pre>${escapeHtml(artifact.content || '')}</pre>
      </details>
      <details>
        <summary>查看元数据</summary>
        ${renderJsonPreview(artifact.metadata || {})}
      </details>
    </section>
  `;
}

export function renderTaskList(tasks, { limit = 6 } = {}) {
  if (!tasks.length) {
    return '<div class="empty-state compact">暂无相关任务。</div>';
  }
  const items = [...tasks].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, limit);
  return items.map((task) => `
    <article class="task-card compact">
      <div class="task-card-head">
        ${badge(task.status, task.status === 'failed' ? 'danger' : task.status === 'completed' ? 'success' : 'accent')}
        ${badge(task.task_name, 'soft')}
      </div>
      <div class="muted">创建于 ${escapeHtml(formatDate(task.created_at))}</div>
      ${task.error ? `<div class="notice error">${escapeHtml(task.error)}</div>` : ''}
    </article>
  `).join('');
}

export function renderChecklist(step) {
  const items = getStepMeta(step).reviewPoints || [];
  if (!items.length) {
    return '<div class="empty-state compact">暂无审查清单。</div>';
  }
  return `
    <ul class="checklist">
      ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
    </ul>
  `;
}

export function renderDependencyList(step, dependencyMap, snapshot, selection = {}) {
  const dependencies = getStepDependencies(step, dependencyMap);
  if (!dependencies.length) {
    return '<div class="empty-state compact">这个对象没有前置依赖。</div>';
  }

  return `
    <div class="stack-list">
      ${dependencies.map((dependency) => {
        const dependencySelection = dependencySelectionFor(step, dependency, selection);
        const ready = Boolean(getArtifactForStep(snapshot, dependency, dependencySelection));
        return `
          <div class="dependency-row">
            <span>${escapeHtml(getStepLabel(dependency))}</span>
            ${badge(ready ? '已就绪' : '缺失', ready ? 'success' : 'danger')}
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function normalizeSubmittedSelection(selection = {}, payload = {}) {
  return normalizeScopeSelection(selection, payload);
}

function buildBaseArtifactPayload(step, snapshot, selection = {}, payload = {}) {
  if (!snapshot) {
    return null;
  }

  const submittedSelection = normalizeSubmittedSelection(selection, payload);

  const attachArtifact = (artifact, sourceStep) => {
    if (!artifact) {
      return null;
    }
    return {
      source_step: sourceStep,
      artifact_key: artifact.key,
      artifact_title: artifact.title,
      artifact_content: artifact.content,
      artifact_summary: artifact.summary,
      artifact_metadata: artifact.metadata,
    };
  };

  if (step === 'volume_outline') {
    return attachArtifact(getArtifact(snapshot, 'rough_volume_outline'), 'rough_volume_outline');
  }
  if (step === 'chapter_plan') {
    return attachArtifact(getScopedArtifact(snapshot, 'rough_chapter_plan', submittedSelection), 'rough_chapter_plan');
  }
  return null;
}

export async function runStepFromForm({ projectId, step, form, snapshot = null, selection = {}, onProgress }) {
  const payload = serializeStepPayload(form, step);
  const baseArtifact = buildBaseArtifactPayload(step, snapshot, selection, payload);
  if (baseArtifact) {
    payload.base_artifact = baseArtifact;
  }
  const endpoint = getStepMeta(step).endpoint;
  if (!endpoint) {
    throw new Error(`步骤 ${step} 没有可用的接口。`);
  }
  onProgress?.('任务已提交，正在执行...');
  const task = await endpoint(projectId, payload);
  const finishedTask = await waitForTask(task.task_id);
  if (finishedTask.status === 'failed') {
    throw new Error(finishedTask.error || '任务执行失败');
  }
  onProgress?.(`任务已完成：${finishedTask.status}`);
  return finishedTask;
}

export async function deleteStepArtifact({ projectId, step, artifactKey, label }) {
  const confirmed = window.confirm(`删除“${label}”后，依赖它的后续产物也会被清理。确定继续吗？`);
  if (!confirmed) {
    return null;
  }
  const targetKey = artifactKey || step;
  if (!targetKey) {
    throw new Error('缺少真实的产物键。');
  }
  return api.deleteProjectArtifact(projectId, targetKey);
}

export function renderStageOverview(steps, snapshot, dependencyMap, tasks = [], selection = {}) {
  return steps.map((step) => {
    const status = getStepStatus(step, snapshot, dependencyMap, tasks, selection);
    const artifact = getArtifactForStep(snapshot, step, selection);
    return `
      <article class="stat-card">
        <div class="stat-card-head">
          <h3>${escapeHtml(getStepLabel(step))}</h3>
          ${badge(status.text, status.tone)}
        </div>
        <p class="muted">${escapeHtml(getStepMeta(step).description || '')}</p>
        <div class="stat-card-foot">${escapeHtml(artifact ? truncate(artifact.content, 72) : '尚未生成结果')}</div>
      </article>
    `;
  }).join('');
}
