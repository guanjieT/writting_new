import { getArtifact, getScopedArtifact } from './artifact-selectors.js';

function cleanOutlineLine(value) {
  return String(value || '')
    .replace(/^[-•*\s]+/, '')
    .trim();
}

function parseChineseNumber(value) {
  const map = {
    '零': 0,
    '一': 1,
    '二': 2,
    '两': 2,
    '三': 3,
    '四': 4,
    '五': 5,
    '六': 6,
    '七': 7,
    '八': 8,
    '九': 9,
  };
  const text = String(value || '').trim();
  if (!text) {
    return 0;
  }
  if (/^\d+$/.test(text)) {
    return Number(text);
  }
  let total = 0;
  let current = 0;
  for (const char of text) {
    if (char === '十') {
      total += (current || 1) * 10;
      current = 0;
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(map, char)) {
      current = map[char];
    }
  }
  return total + current;
}

export function getGeneratedStructuredPayload(artifact) {
  const generatedPayload = artifact?.metadata?.generated_payload;
  if (generatedPayload && typeof generatedPayload.structured === 'object' && generatedPayload.structured !== null) {
    return generatedPayload.structured;
  }
  const summaryStructured = artifact?.summary?.structured;
  if (summaryStructured && typeof summaryStructured === 'object') {
    return summaryStructured;
  }
  return null;
}

export function parseOutlineVolumeSections(snapshot) {
  const outlineArtifact = getArtifact(snapshot, 'rough_volume_outline') || getArtifact(snapshot, 'outline');
  const structured = getGeneratedStructuredPayload(outlineArtifact);
  if (structured && Array.isArray(structured.volumes) && structured.volumes.length) {
    return structured.volumes
      .map((item, index) => ({
        index: Number(item?.volume_index || index + 1) || index + 1,
        title: String(item?.title || '').trim(),
        goal: String(item?.goal || '').trim(),
        conflict: String(item?.main_conflict || '').trim(),
        hook: String(item?.ending_hook || '').trim(),
        chapter_briefs: Array.isArray(item?.chapter_briefs) ? item.chapter_briefs.map((brief) => cleanOutlineLine(brief)).filter(Boolean) : [],
        target_chapter_count: Number(item?.target_chapter_count || 0) || 0,
        target_words: Number(item?.target_words || 0) || 0,
      }))
      .filter((item) => item.index > 0);
  }
  const generatedContent = outlineArtifact?.metadata?.generated_payload?.content || outlineArtifact?.content || '';
  const text = String(generatedContent || '').trim();
  if (!text) {
    return [];
  }

  const sections = [];
  let current = null;
  let inChapterBriefs = false;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    const headingMatch = line.match(/^第([一二三四五六七八九十百零两\d]+)卷[:：]\s*(.+)$/);
    if (headingMatch) {
      if (current) {
        sections.push(current);
      }
      current = {
        index: parseChineseNumber(headingMatch[1]),
        title: headingMatch[2].trim(),
        goal: '',
        conflict: '',
        hook: '',
        chapter_briefs: [],
      };
      inChapterBriefs = false;
      continue;
    }

    if (!current) {
      continue;
    }

    const goalMatch = line.match(/^[\-•*\s]*卷级目标[:：]\s*(.+)$/);
    if (goalMatch) {
      current.goal = goalMatch[1].trim();
      continue;
    }

    const conflictMatch = line.match(/^[\-•*\s]*卷级冲突[:：]\s*(.+)$/);
    if (conflictMatch) {
      current.conflict = conflictMatch[1].trim();
      continue;
    }

    const hookMatch = line.match(/^[\-•*\s]*卷尾钩子[:：]\s*(.+)$/);
    if (hookMatch) {
      current.hook = hookMatch[1].trim();
      continue;
    }

    if (/^[\-•*\s]*章节粗计划[:：]\s*$/.test(line)) {
      inChapterBriefs = true;
      continue;
    }

    if (/^[\-•*\s]*章节粗计划[:：]\s*(.+)$/.test(line)) {
      inChapterBriefs = true;
      const brief = cleanOutlineLine(line.replace(/^[\-•*\s]*章节粗计划[:：]\s*/, ''));
      if (brief) {
        current.chapter_briefs.push(brief);
      }
      continue;
    }

    if (inChapterBriefs) {
      const brief = cleanOutlineLine(line);
      if (brief) {
        current.chapter_briefs.push(brief);
      }
    }
  }

  if (current) {
    sections.push(current);
  }

  return sections;
}

function parseRoughChapterPlanSections(snapshot, volumeIndex = 1) {
  const roughArtifact = getScopedArtifact(snapshot, 'rough_chapter_plan', { volumeIndex });
  const structured = getGeneratedStructuredPayload(roughArtifact);
  if (structured && Array.isArray(structured.chapters) && structured.chapters.length) {
    return structured.chapters
      .map((item, index) => ({
        index: Number(item?.chapter_index || index + 1) || index + 1,
        title: String(item?.title || '').trim(),
        summary: String(item?.summary || '').trim(),
        chapter_type: String(item?.chapter_type || '').trim(),
        pov_character: String(item?.pov_character || '').trim(),
        conflict: String(item?.conflict || '').trim(),
        hook: String(item?.hook || '').trim(),
        scene_summaries: Array.isArray(item?.scene_summaries) ? item.scene_summaries.map((scene) => cleanOutlineLine(scene)).filter(Boolean) : [],
        main_event: String(item?.main_event || '').trim(),
        target_words: Number(item?.target_words || 0) || 0,
      }))
      .filter((item) => item.index > 0);
  }
  const generatedContent = roughArtifact?.metadata?.generated_payload?.content || roughArtifact?.content || '';
  const text = String(generatedContent || '').trim();
  if (!text) {
    return [];
  }

  const chapters = [];
  let current = null;
  let inScenes = false;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    const chapterMatch = line.match(/^第([一二三四五六七八九十百零两\d]+)章[:：]\s*(.+)$/);
    if (chapterMatch) {
      if (current) {
        chapters.push(current);
      }
      current = {
        index: parseChineseNumber(chapterMatch[1]),
        title: chapterMatch[2].trim(),
        summary: '',
        chapter_type: '',
        pov_character: '',
        conflict: '',
        hook: '',
        scene_summaries: [],
      };
      inScenes = false;
      continue;
    }

    if (!current) {
      continue;
    }

    const summaryMatch = line.match(/^[\-•*\s]*章节摘要[:：]\s*(.+)$/);
    if (summaryMatch) {
      current.summary = summaryMatch[1].trim();
      continue;
    }

    const typeMatch = line.match(/^[\-•*\s]*章节类型[:：]\s*(.+)$/);
    if (typeMatch) {
      current.chapter_type = typeMatch[1].trim();
      continue;
    }

    const povMatch = line.match(/^[\-•*\s]*视角人物[:：]\s*(.+)$/);
    if (povMatch) {
      current.pov_character = povMatch[1].trim();
      continue;
    }

    const conflictMatch = line.match(/^[\-•*\s]*核心冲突[:：]\s*(.+)$/);
    if (conflictMatch) {
      current.conflict = conflictMatch[1].trim();
      continue;
    }

    const hookMatch = line.match(/^[\-•*\s]*章节钩子[:：]\s*(.+)$/);
    if (hookMatch) {
      current.hook = hookMatch[1].trim();
      continue;
    }

    if (/^[\-•*\s]*场景粗纲[:：]\s*$/.test(line) || /^[\-•*\s]*场景摘要[:：]\s*$/.test(line)) {
      inScenes = true;
      continue;
    }

    if (/^[\-•*\s]*场景粗纲[:：]\s*(.+)$/.test(line) || /^[\-•*\s]*场景摘要[:：]\s*(.+)$/.test(line)) {
      inScenes = true;
      const scene = cleanOutlineLine(line.replace(/^[\-•*\s]*(场景粗纲|场景摘要)[:：]\s*/, ''));
      if (scene) {
        current.scene_summaries.push(scene);
      }
      continue;
    }

    if (inScenes) {
      const scene = cleanOutlineLine(line);
      if (scene) {
        current.scene_summaries.push(scene);
      }
    }
  }

  if (current) {
    chapters.push(current);
  }

  return chapters;
}

export function extractRoughChapterPlanChapterCount(snapshot, volumeIndex = 1) {
  const roughArtifact = getScopedArtifact(snapshot, 'rough_chapter_plan', { volumeIndex });
  const structured = getGeneratedStructuredPayload(roughArtifact);
  if (structured && Array.isArray(structured.chapters) && structured.chapters.length) {
    const explicitCount = Number(structured.total_target_chapters || 0) || 0;
    return explicitCount > 0 ? explicitCount : structured.chapters.length;
  }
  return parseRoughChapterPlanSections(snapshot, volumeIndex).length;
}

export function extractVolumeOutlineDefaults(snapshot, volumeIndex = 1) {
  const sections = parseOutlineVolumeSections(snapshot);
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
  const chapters = parseRoughChapterPlanSections(snapshot, volumeIndex);
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
