import { getScopedArtifact } from './artifact-selectors.js';
import { textFromList } from './state.js';
import {
  getGeneratedStructuredPayload,
  getRoughChapterPlanChapterCount,
  parseRoughChapterPlanChapters,
  parseRoughVolumeOutlineVolumes,
} from './structured-parsers.js';

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

function positiveNumber(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0;
}

function extractVolumeOutlineChapterCount(snapshot, volumeIndex = 1) {
  const artifact = getScopedArtifact(snapshot, 'volume_outline', { volumeIndex });
  const structured = getGeneratedStructuredPayload(artifact);
  return positiveNumber(structured?.target_chapter_count);
}

export function extractVolumeOutlineDefaults(snapshot, volumeIndex = 1) {
  const sections = parseRoughVolumeOutlineVolumes(snapshot);
  if (!sections.length) {
    return null;
  }

  const safeIndex = Math.max(Number(volumeIndex) || 1, 1);
  const selected = sections.find((section) => section.index === safeIndex) || sections[0];
  if (!selected) {
    return null;
  }

  const chapterCountFromBriefs = selected.chapter_briefs.reduce((maxValue, brief) => {
    const match = brief.match(/(\d+)(?:\s*[-~—]\s*(\d+))?\s*章/);
    if (!match) {
      return maxValue;
    }
    const endValue = Number(match[2] || match[1]) || 0;
    return Math.max(maxValue, endValue);
  }, 0);

  const summaryParts = [selected.goal, selected.conflict, selected.hook].filter(Boolean);
  return {
    volume_title: selected.title || '',
    volume_summary: summaryParts.join('；'),
    volume_goal: selected.goal || '',
    volume_conflict: selected.conflict || '',
    volume_hook: selected.hook || '',
    chapter_briefs: selected.chapter_briefs,
    target_chapter_count: selected.target_chapter_count || chapterCountFromBriefs || selected.chapter_briefs.length || 0,
  };
}

export function extractChapterPlanDefaults(snapshot, volumeIndex = 1, chapterIndex = 1) {
  const chapters = parseRoughChapterPlanChapters(snapshot, volumeIndex);
  if (!chapters.length) {
    return null;
  }

  const safeIndex = Math.max(Number(chapterIndex) || 1, 1);
  const selected = chapters.find((chapter) => chapter.index === safeIndex) || chapters[0];
  if (!selected) {
    return null;
  }

  return {
    volume_index: Math.max(Number(volumeIndex) || 1, 1),
    chapter_index: selected.index,
    chapter_title: selected.title || '',
    chapter_summary: selected.summary || '',
    chapter_type: selected.chapter_type || '主线推进章',
    pov_character: selected.pov_character || '',
    conflict: selected.conflict || '',
    hook: selected.hook || '',
    scene_summaries: selected.scene_summaries,
    main_event: selected.main_event || '',
    target_words: selected.target_words || 0,
  };
}

export function extractChapterDraftDefaults(snapshot, volumeIndex = 1, chapterIndex = 1) {
  const artifact = getScopedArtifact(snapshot, 'chapter_plan', { volumeIndex, chapterIndex });
  const structured = getGeneratedStructuredPayload(artifact);
  if (!structured) {
    return null;
  }

  const sceneSummaries = Array.isArray(structured.scene_summaries)
    ? structured.scene_summaries.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  const continuityNotes = Array.isArray(structured.continuity_notes)
    ? structured.continuity_notes.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  const writingNotes = Array.isArray(structured.writing_notes)
    ? structured.writing_notes.map((item) => String(item || '').trim()).filter(Boolean)
    : [];

  return {
    chapter_goal: String(structured.summary || structured.main_event || artifact?.summary?.overview || '').trim(),
    scene_beats: sceneSummaries,
    notes: [...continuityNotes, ...writingNotes],
    target_words: positiveNumber(structured.target_words),
  };
}

export function inferChapterCountForVolume(snapshot, volumeIndex = 1) {
  return getRoughChapterPlanChapterCount(snapshot, volumeIndex)
    || extractVolumeOutlineChapterCount(snapshot, volumeIndex)
    || extractVolumeOutlineDefaults(snapshot, volumeIndex)?.target_chapter_count
    || snapshot?.project?.input?.target_chapters_per_volume
    || 12;
}

function renderInputValue(field, project, snapshot, selection = {}) {
  const projectInput = project?.input || {};
  const volumeIndex = Number(selection.volumeIndex || selection.volume_index || 1) || 1;
  const chapterIndex = Number(selection.chapterIndex || selection.chapter_index || 1) || 1;

  if (field.key === 'volume_index') {
    return Math.max(volumeIndex, 1);
  }
  if (field.key === 'chapter_index') {
    return Math.max(chapterIndex, 1);
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
    const outlineDefaults = extractVolumeOutlineDefaults(snapshot, volumeIndex);
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
    return extractVolumeOutlineChapterCount(snapshot, volumeIndex)
      || extractVolumeOutlineDefaults(snapshot, volumeIndex)?.target_chapter_count
      || projectInput.target_chapters_per_volume
      || 12;
  }
  if (field.stepKey === 'chapter_plan') {
    const chapterDefaults = extractChapterPlanDefaults(snapshot, volumeIndex, chapterIndex);
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
  if (field.stepKey === 'chapter') {
    const draftDefaults = extractChapterDraftDefaults(snapshot, volumeIndex, chapterIndex);
    if (draftDefaults) {
      if (field.key === 'chapter_goal') {
        return draftDefaults.chapter_goal || '';
      }
      if (field.key === 'scene_beats') {
        return draftDefaults.scene_beats || [];
      }
      if (field.key === 'notes' && draftDefaults.notes?.length) {
        return [
          ...draftDefaults.notes,
          ...collectProjectListValues(projectInput, PROJECT_NOTE_SOURCES.chapter),
        ];
      }
      if (field.key === 'target_words' && draftDefaults.target_words) {
        return draftDefaults.target_words;
      }
    }
  }
  if (field.key === 'chapters_per_volume' || field.key === 'target_chapter_count') {
    return inferChapterCountForVolume(snapshot, volumeIndex);
  }
  if (field.key === 'target_words') {
    const volumeCount = Math.max(projectInput.target_volume_count || 1, 1);
    const chaptersPerVolume = Math.max(inferChapterCountForVolume(snapshot, volumeIndex) || 1, 1);
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
