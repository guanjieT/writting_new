import { textFromList } from './state.js';
import { extractChapterPlanDefaults, extractVolumeOutlineDefaults } from './structured-parsers.js';

const PROJECT_NOTE_SOURCES = {
  requirements: ['core_requirements', 'forbidden_elements'],
  story_bible: ['tone', 'style'],
  characters: ['core_requirements', 'forbidden_elements', 'outline_focus'],
  outline: ['outline_focus', 'core_requirements', 'forbidden_elements'],
  rough_volume_outline: ['outline_focus', 'core_requirements', 'forbidden_elements'],
  volume_outline: ['outline_focus', 'core_requirements'],
  rough_chapter_plan: ['outline_focus', 'core_requirements'],
  chapter_plan: ['core_requirements', 'forbidden_elements'],
  chapter: ['core_requirements', 'forbidden_elements'],
  revision: ['core_requirements', 'forbidden_elements'],
  consistency: ['outline_focus', 'core_requirements', 'forbidden_elements'],
  memory: ['core_requirements', 'forbidden_elements'],
};

function collectProjectListValues(projectInput, keys) {
  return keys
    .flatMap((key) => (Array.isArray(projectInput[key]) ? projectInput[key] : []))
    .map((item) => String(item || '').trim())
    .filter(Boolean);
}

function renderInputValue(field, project, snapshot, selection = {}) {
  const projectInput = project?.input || {};
  if (field.key === 'volume_index') {
    return Math.max(Number(selection.volumeIndex || selection.volume_index || 1) || 1, 1);
  }
  if (field.key === 'chapter_index') {
    return Math.max(Number(selection.chapterIndex || selection.chapter_index || 1) || 1, 1);
  }
  if (field.key === 'requirements_text') {
    return projectInput.premise || '';
  }
  if (field.key === 'audience') {
    return projectInput.target_audience || '';
  }
  if (field.key === 'volume_count') {
    return projectInput.target_volume_count || 1;
  }
  if (field.stepKey === 'volume_outline') {
    const outlineDefaults = extractVolumeOutlineDefaults(snapshot, Number(selection.volumeIndex || selection.volume_index || 1) || 1);
    if (outlineDefaults) {
      if (field.key === 'volume_title') {
        return outlineDefaults.volume_title || '';
      }
      if (field.key === 'volume_summary') {
        return outlineDefaults.volume_summary || '';
      }
      if (field.key === 'volume_goal') {
        return outlineDefaults.volume_goal || '';
      }
      if (field.key === 'volume_conflict') {
        return outlineDefaults.volume_conflict || '';
      }
      if (field.key === 'volume_hook') {
        return outlineDefaults.volume_hook || '';
      }
      if (field.key === 'chapter_briefs') {
        return outlineDefaults.chapter_briefs || [];
      }
      if (field.key === 'target_chapter_count' && outlineDefaults.target_chapter_count) {
        return outlineDefaults.target_chapter_count;
      }
    }
  }
  if (field.stepKey === 'rough_chapter_plan' && field.key === 'target_chapter_count') {
    const outlineDefaults = extractVolumeOutlineDefaults(snapshot, Number(selection.volumeIndex || selection.volume_index || 1) || 1);
    return outlineDefaults?.target_chapter_count || projectInput.target_chapters_per_volume || 12;
  }
  if (field.stepKey === 'chapter_plan') {
    const chapterDefaults = extractChapterPlanDefaults(snapshot, Number(selection.volumeIndex || selection.volume_index || 1) || 1, Number(selection.chapterIndex || selection.chapter_index || 1) || 1);
    if (chapterDefaults) {
      if (field.key === 'chapter_title') {
        return chapterDefaults.chapter_title || '';
      }
      if (field.key === 'chapter_summary') {
        return chapterDefaults.chapter_summary || '';
      }
      if (field.key === 'chapter_type') {
        return chapterDefaults.chapter_type || '主线推进章';
      }
      if (field.key === 'pov_character') {
        return chapterDefaults.pov_character || '';
      }
      if (field.key === 'conflict') {
        return chapterDefaults.conflict || '';
      }
      if (field.key === 'hook') {
        return chapterDefaults.hook || '';
      }
      if (field.key === 'scene_summaries') {
        return chapterDefaults.scene_summaries || [];
      }
    }
  }
  if (field.key === 'chapters_per_volume' || field.key === 'target_chapter_count') {
    const outlineDefaults = extractVolumeOutlineDefaults(snapshot, Number(selection.volumeIndex || selection.volume_index || 1) || 1);
    return outlineDefaults?.target_chapter_count || projectInput.target_chapters_per_volume || 12;
  }
  if (field.key === 'target_words') {
    const volumeCount = Math.max(projectInput.target_volume_count || 1, 1);
    const chaptersPerVolume = Math.max(projectInput.target_chapters_per_volume || 1, 1);
    if (['chapter', 'chapter_plan'].includes(field.stepKey)) {
      return Math.max(Math.floor((projectInput.target_words || 0) / (volumeCount * chaptersPerVolume)), 2000);
    }
    if (field.stepKey === 'volume_outline') {
      return Math.max(Math.floor((projectInput.target_words || 0) / volumeCount), 0);
    }
  }
  if (field.key === 'focus_points') {
    return projectInput.outline_focus || [];
  }
  if (field.key === 'known_rules') {
    return collectProjectListValues(projectInput, ['outline_focus', 'core_requirements', 'forbidden_elements']);
  }
  if (field.key === 'notes' && field.stepKey && PROJECT_NOTE_SOURCES[field.stepKey]) {
    return collectProjectListValues(projectInput, PROJECT_NOTE_SOURCES[field.stepKey]);
  }
  if (field.defaultValue !== undefined && field.defaultValue !== null && field.defaultValue !== '') {
    return field.defaultValue;
  }
  if (field.type === 'checkbox') {
    return Boolean(field.defaultValue);
  }
  return '';
}

export function getFieldDisplayValue(field, project, snapshot, selection = {}) {
  const enhancedField = { ...field, stepKey: field.stepKey || '' };
  const value = renderInputValue(enhancedField, project, snapshot, selection);
  return field.list ? textFromList(value) : value;
}

export { renderInputValue, extractVolumeOutlineDefaults, extractChapterPlanDefaults };
