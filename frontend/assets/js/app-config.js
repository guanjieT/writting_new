import { api } from './api-client.js';
import { listFromText, textFromList } from './state.js';

export const FALLBACK_WORKFLOW_STEPS = [
  { key: 'requirements', label: '需求分析', depends_on: [] },
  { key: 'story_bible', label: '世界观设定', depends_on: ['requirements'] },
  { key: 'characters', label: '角色框架', depends_on: ['requirements', 'story_bible'] },
  { key: 'outline', label: '总纲', depends_on: ['requirements', 'story_bible', 'characters'] },
  { key: 'rough_volume_outline', label: '粗卷纲', depends_on: ['outline'] },
  { key: 'volume_outline', label: '完善卷纲', depends_on: ['rough_volume_outline'] },
  { key: 'rough_chapter_plan', label: '粗章纲', depends_on: ['volume_outline'] },
  { key: 'chapter_plan', label: '完善章节计划', depends_on: ['rough_chapter_plan'] },
  { key: 'chapter', label: '章节生成', depends_on: ['chapter_plan'] },
  { key: 'revision', label: '修订', depends_on: ['chapter'] },
  { key: 'consistency', label: '一致性检查', depends_on: ['chapter'] },
  { key: 'memory', label: '记忆整理', depends_on: ['chapter'] },
];

export const STEP_META = {
  requirements: {
    label: '需求定位',
    group: 'setting',
    page: 'workflow',
    description: '把作品目标、边界和必须满足的约束先说清楚，避免后面所有环节都建立在模糊前提上。',
    objectName: '作品需求单',
    reviewPoints: ['主目标是否单一明确', '受众定位是否清晰', '禁忌与硬约束是否已经落地'],
    fields: [
      { key: 'requirements_text', label: '需求描述', type: 'textarea', rows: 6, placeholder: '这本书最想实现什么？要解决什么写作目标？' },
      { key: 'audience', label: '目标受众', type: 'text', placeholder: '例如：男频成长流读者 / 女性向群像读者' },
      { key: 'notes', label: '补充约束', type: 'textarea', rows: 4, list: true, placeholder: '一行一条，例如：\n必须有家族权力斗争\n不能采用第一人称' },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runRequirements,
  },
  story_bible: {
    label: '世界与规则',
    group: 'setting',
    page: 'workflow',
    description: '把世界规则、主题母题和运行逻辑沉淀为故事圣经，方便后续角色与结构统一。',
    objectName: '世界观资产',
    reviewPoints: ['世界规则是否可执行', '主题是否和题材匹配', '设定是否已经足够支撑长篇推进'],
    fields: [
      { key: 'theme', label: '主题母题', type: 'text', placeholder: '例如：权力的代价 / 失序世界中的重建' },
      { key: 'world_rules', label: '世界规则', type: 'textarea', rows: 6, list: true, placeholder: '一行一条，例如：\n修炼体系分九阶\n货币与灵石绑定' },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true, placeholder: '对社会结构、力量来源、势力边界的补充说明' },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runStoryBible,
  },
  characters: {
    label: '角色框架',
    group: 'setting',
    page: 'workflow',
    description: '先固定核心角色，再保留可生长角色槽位，避免开局把所有人物锁死。',
    objectName: '角色框架',
    reviewPoints: ['男女主和终反派是否明确', '角色槽位是否保留了后续生长空间', '角色规则是否足够稳定'],
    fields: [
      { key: 'role_capacity', label: '角色容量参考', type: 'number', defaultValue: 4, placeholder: '只做规模提示，不是硬性上限' },
      { key: 'core_roles', label: '核心角色', type: 'textarea', rows: 4, list: true, placeholder: '一行一位，优先填男女主、最终反派、必需支点角色' },
      { key: 'role_slots', label: '角色槽位', type: 'textarea', rows: 5, list: true, placeholder: '一行一个槽位，例如：导师位 / 竞争者位 / 线人位 / 牺牲者位' },
      { key: 'role_rules', label: '角色生长规则', type: 'textarea', rows: 4, list: true, placeholder: '一行一条，例如：\n每卷最多新增两个长期角色\n新角色必须对应具体剧情事件' },
      { key: 'notes', label: '角色补充约束', type: 'textarea', rows: 4, list: true, placeholder: '例如：女主不能工具化；终反派必须有完整利益逻辑' },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runCharacters,
  },
  outline: {
    label: '总纲',
    group: 'structure',
    page: 'outline',
    description: '先定义全书级别的目标、节奏和阶段推进，再为后续粗卷纲提供总蓝图。',
    objectName: '总纲',
    reviewPoints: ['开端—发展—转折—收束是否成链', '全书目标与题材预期是否一致', '是否足以支撑后续卷级拆解'],
    fields: [
      { key: 'volume_count', label: '目标卷数', type: 'number', defaultValue: 1 },
      { key: 'chapters_per_volume', label: '每卷章节数', type: 'number', defaultValue: 12 },
      { key: 'focus_points', label: '总纲关注点', type: 'textarea', rows: 5, list: true, placeholder: '例如：主线升级节奏、世界揭秘节点、核心人物弧光' },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1400, advanced: true },
    ],
    endpoint: api.runOutline,
  },
  rough_volume_outline: {
    label: '粗卷纲',
    group: 'structure',
    page: 'outline',
    description: '一次生成全书所有卷的粗略结构，不拆成单卷。',
    objectName: '粗卷纲',
    reviewPoints: ['是否覆盖所有卷', '卷间节奏是否连贯', '每卷是否保留后续细化空间'],
    fields: [
      { key: 'volume_count', label: '目标卷数', type: 'number', defaultValue: 1 },
      { key: 'chapters_per_volume', label: '每卷章节数', type: 'number', defaultValue: 12 },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1600, advanced: true },
    ],
    endpoint: api.runRoughVolumeOutline,
  },
  volume_outline: {
    label: '完善卷纲',
    group: 'structure',
    page: 'volume-outline',
    description: '基于粗卷纲，完善当前卷的完整卷纲。',
    objectName: '卷纲',
    reviewPoints: ['卷目标是否独立完整', '是否与粗卷纲对应', '是否可直接进入粗章纲阶段'],
    fields: [
      { key: 'volume_index', label: '卷序号', type: 'number', defaultValue: 1 },
      { key: 'volume_title', label: '卷标题', type: 'text', placeholder: '例如：第一卷·入局' },
      { key: 'volume_summary', label: '卷摘要', type: 'textarea', rows: 5 },
      { key: 'volume_goal', label: '卷目标', type: 'text' },
      { key: 'volume_conflict', label: '卷冲突', type: 'textarea', rows: 4 },
      { key: 'volume_hook', label: '卷尾钩子', type: 'textarea', rows: 3 },
      { key: 'target_words', label: '卷目标字数', type: 'number', defaultValue: 0 },
      { key: 'target_chapter_count', label: '卷目标章节数', type: 'number', defaultValue: 0 },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1400, advanced: true },
    ],
    endpoint: api.runVolumeOutline,
  },
  rough_chapter_plan: {
    label: '粗章纲',
    group: 'structure',
    page: 'volume-outline',
    description: '一次生成当前卷所有章节的粗计划。',
    objectName: '粗章纲',
    reviewPoints: ['卷内章节节奏是否成链', '章节之间是否有铺垫和呼应', '是否保留了细化空间'],
    fields: [
      { key: 'volume_index', label: '卷序号', type: 'number', defaultValue: 1 },
      { key: 'target_chapter_count', label: '章节数', type: 'number', defaultValue: 0 },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1600, advanced: true },
    ],
    endpoint: api.runRoughChapterPlan,
  },
  chapter_plan: {
    label: '完善章节计划',
    group: 'structure',
    page: 'chapter-plan',
    description: '基于粗章纲，完善当前章的完整章节计划。',
    objectName: '章节计划',
    reviewPoints: ['章节目标是否单一', '是否与粗章纲对应', '是否已细化到可直接写作'],
    fields: [
      { key: 'volume_index', label: '卷序号', type: 'number', defaultValue: 1 },
      { key: 'chapter_index', label: '章节序号', type: 'number', defaultValue: 1 },
      { key: 'chapter_title', label: '章节标题', type: 'text' },
      { key: 'chapter_summary', label: '章节摘要', type: 'textarea', rows: 5 },
      { key: 'chapter_type', label: '章节类型', type: 'text', defaultValue: '主线推进章' },
      { key: 'pov_character', label: '视角人物', type: 'text' },
      { key: 'protagonist_present', label: '主角在场', type: 'checkbox', defaultValue: true },
      { key: 'conflict', label: '核心冲突', type: 'textarea', rows: 3 },
      { key: 'hook', label: '章节钩子', type: 'textarea', rows: 3 },
      { key: 'target_words', label: '目标字数', type: 'number', defaultValue: 3000 },
      { key: 'min_words', label: '最低字数', type: 'number', defaultValue: 2000 },
      { key: 'characters', label: '本章人物', type: 'textarea', rows: 3, list: true },
      { key: 'introduced_characters', label: '新登场人物', type: 'textarea', rows: 3, list: true },
      { key: 'scene_summaries', label: '场景摘要', type: 'textarea', rows: 5, list: true },
      { key: 'plan_notes', label: '计划备注', type: 'textarea', rows: 3 },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 3, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runChapterPlan,
  },
  chapter: {
    label: '章节正文',
    group: 'writing',
    page: 'workflow',
    description: '这里只负责把已确认的章节计划落成正文，不再承担结构探索。',
    objectName: '章节正文',
    reviewPoints: ['本章目标是否落地', '节奏是否符合章节计划', '场景推进是否清晰'],
    fields: [
      { key: 'volume_index', label: '卷序号', type: 'number', defaultValue: 1 },
      { key: 'chapter_index', label: '章节序号', type: 'number', defaultValue: 1 },
      { key: 'chapter_goal', label: '章节目标', type: 'text', placeholder: '一句话写清本章完成什么推进' },
      { key: 'target_words', label: '目标字数', type: 'number', defaultValue: 2000 },
      { key: 'scene_beats', label: '场景节拍', type: 'textarea', rows: 5, list: true, placeholder: '一行一段节拍，例如：\n遭遇伏击\n被迫结盟\n留下误导线索' },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1600, advanced: true },
    ],
    endpoint: api.runChapter,
  },
  revision: {
    label: '正文修订',
    group: 'writing',
    page: 'workflow',
    description: '修订是针对已有正文的质量调整，不是重新生成世界观或总纲。',
    objectName: '修订结果',
    reviewPoints: ['修订目标是否具体', '是否只改需要改的部分', '是否保住了原有结构作用'],
    fields: [
      { key: 'target_artifact', label: '目标产物键', type: 'text', defaultValue: 'chapter' },
      { key: 'instruction', label: '修订指令', type: 'textarea', rows: 5, placeholder: '例如：压缩说明性段落，增强人物对话中的冲突感' },
      { key: 'focus_areas', label: '修订关注点', type: 'textarea', rows: 4, list: true, placeholder: '一行一条，例如：\n节奏\n人物动机\n结尾钩子' },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runRevision,
  },
  consistency: {
    label: '一致性检查',
    group: 'review',
    page: 'workflow',
    description: '把角色、设定、时间线和正文进行交叉检查，找出冲突点。',
    objectName: '一致性报告',
    reviewPoints: ['是否覆盖设定与人物', '是否指出具体冲突', '问题是否可追溯到上游资产'],
    fields: [
      { key: 'scope', label: '检查范围', type: 'text', defaultValue: 'project' },
      { key: 'known_rules', label: '已知规则', type: 'textarea', rows: 5, list: true, placeholder: '可填已知设定规则，帮助报告更聚焦' },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1200, advanced: true },
    ],
    endpoint: api.runConsistency,
  },
  memory: {
    label: '记忆整理',
    group: 'review',
    page: 'workflow',
    description: '把已生成内容里的关键信息重新组织出来，方便后续长篇续写时检索。',
    objectName: '记忆摘要',
    reviewPoints: ['是否抓到关键事实', '是否方便后续引用', '是否遗漏关键角色与规则'],
    fields: [
      { key: 'query', label: '检索问题', type: 'text', placeholder: '例如：主角在第一卷中已暴露了哪些秘密？' },
      { key: 'top_k', label: '返回条目数', type: 'number', defaultValue: 5 },
      { key: 'notes', label: '补充说明', type: 'textarea', rows: 4, list: true },
      { key: 'temperature', label: '生成温度', type: 'number', step: '0.1', defaultValue: 0.7, advanced: true },
      { key: 'max_tokens', label: '最大输出', type: 'number', defaultValue: 1000, advanced: true },
    ],
    endpoint: api.runMemory,
  },
};

export const PAGE_STEP_GROUPS = {
  workflow: [
    { key: 'setting', label: '设定资产', steps: ['requirements', 'story_bible', 'characters'] },
    { key: 'writing', label: '正文推进', steps: ['chapter', 'revision', 'consistency', 'memory'] },
  ],
  outline: [
    { key: 'structure', label: '全书结构', steps: ['outline', 'rough_volume_outline'] },
  ],
  'volume-outline': [
    { key: 'structure', label: '卷级结构', steps: ['volume_outline', 'rough_chapter_plan'] },
  ],
  'chapter-plan': [
    { key: 'structure', label: '章级结构', steps: ['chapter_plan'] },
  ],
};

export const REVIEW_GROUPS = [
  { key: 'setting', label: '设定资产', steps: ['requirements', 'story_bible', 'characters'] },
  { key: 'structure-outline', label: '总纲与粗卷纲', steps: ['outline', 'rough_volume_outline'] },
  { key: 'structure-volume', label: '卷纲与粗章纲', steps: ['volume_outline', 'rough_chapter_plan'] },
  { key: 'structure-chapter', label: '章节计划', steps: ['chapter_plan'] },
  { key: 'writing', label: '正文与修订', steps: ['chapter', 'revision'] },
  { key: 'audit', label: '一致性与记忆', steps: ['consistency', 'memory'] },
];

export async function loadWorkflowContext() {
  try {
    const spec = await api.getWorkflowSpec();
    const steps = Array.isArray(spec?.steps) && spec.steps.length ? spec.steps : FALLBACK_WORKFLOW_STEPS;
    const dependencies = spec?.dependencies || Object.fromEntries(steps.map((step) => [step.key, step.depends_on || []]));
    return { steps, dependencies };
  } catch {
    return {
      steps: FALLBACK_WORKFLOW_STEPS,
      dependencies: Object.fromEntries(FALLBACK_WORKFLOW_STEPS.map((step) => [step.key, step.depends_on || []])),
    };
  }
}

export function getStepMeta(step) {
  return STEP_META[step] || { label: step, description: '', fields: [], reviewPoints: [], endpoint: null };
}

export function getStepLabel(step, workflowSteps = FALLBACK_WORKFLOW_STEPS) {
  return getStepMeta(step).label || workflowSteps.find((item) => item.key === step)?.label || step;
}

export function getStepDependencies(step, dependencyMap = {}) {
  return dependencyMap[step] || FALLBACK_WORKFLOW_STEPS.find((item) => item.key === step)?.depends_on || [];
}

export function getArtifact(snapshot, step) {
  const artifacts = getArtifactsForStep(snapshot, step);
  return artifacts.length ? artifacts[artifacts.length - 1] : null;
}

const ARTIFACT_SCOPE_KIND = {
  outline: 'project',
  rough_volume_outline: 'project',
  volume_outline: 'volume',
  rough_chapter_plan: 'volume',
  chapter_plan: 'chapter',
  chapter: 'chapter',
  revision: 'chapter',
  consistency: 'chapter',
  memory: 'chapter',
};

function normalizeScopeSelection(selection = {}) {
  return {
    volumeIndex: Math.max(Number(selection.volumeIndex || selection.volume_index || 1) || 1, 1),
    chapterIndex: Math.max(Number(selection.chapterIndex || selection.chapter_index || 1) || 1, 1),
  };
}

export function getStepScopeKind(step) {
  return ARTIFACT_SCOPE_KIND[step] || 'project';
}

function hasExplicitSelection(selection = {}) {
  return Boolean(
    selection
    && (
      selection.volumeIndex !== undefined
      || selection.volume_index !== undefined
      || selection.chapterIndex !== undefined
      || selection.chapter_index !== undefined
    )
  );
}

export function getArtifactForStep(snapshot, step, selection = {}) {
  if (hasExplicitSelection(selection)) {
    return getScopedArtifact(snapshot, step, selection);
  }
  return getArtifact(snapshot, step);
}

export function getArtifactsForStep(snapshot, step) {
  const artifacts = Object.values(snapshot?.artifacts || {});
  return artifacts.filter((artifact) => artifact?.metadata?.step === step || artifact?.key === step);
}

export function getScopedArtifact(snapshot, step, selection = {}) {
  const scopeKind = getStepScopeKind(step);
  const normalized = normalizeScopeSelection(selection);
  return getArtifactsForStep(snapshot, step).find((artifact) => {
    const metadata = artifact?.metadata || {};
    if ((metadata.scope_kind || 'project') !== scopeKind) {
      return false;
    }
    if (scopeKind === 'volume') {
      return Number(metadata.volume_index || 0) === normalized.volumeIndex;
    }
    if (scopeKind === 'chapter') {
      return Number(metadata.volume_index || 0) === normalized.volumeIndex && Number(metadata.chapter_index || 0) === normalized.chapterIndex;
    }
    return true;
  }) || null;
}

function dependencySelectionFor(step, dependency, selection = {}) {
  if (!hasExplicitSelection(selection)) {
    return {};
  }
  const normalized = normalizeScopeSelection(selection);
  const dependencyScope = getStepScopeKind(dependency);
  if (dependencyScope === 'volume') {
    return { volumeIndex: normalized.volumeIndex };
  }
  if (dependencyScope === 'chapter') {
    return { volumeIndex: normalized.volumeIndex, chapterIndex: normalized.chapterIndex };
  }
  return {};
}

function dependencyArtifactFor(step, dependency, snapshot, selection = {}) {
  return getScopedArtifact(snapshot, dependency, dependencySelectionFor(step, dependency, selection));
}

export function completedSteps(snapshot) {
  return new Set(Object.values(snapshot?.artifacts || {}).map((artifact) => artifact?.metadata?.step || artifact?.key).filter(Boolean));
}

export function isUnlocked(step, snapshot, dependencyMap, selection = {}) {
  return getStepDependencies(step, dependencyMap).every((item) => Boolean(dependencyArtifactFor(step, item, snapshot, selection)));
}

export function getStepStatus(step, snapshot, dependencyMap, tasks = [], selection = {}) {
  const artifact = getArtifactForStep(snapshot, step, selection);
  if (artifact) {
    return artifact?.metadata?.stale ? { tone: 'warn', text: '已失效' } : { tone: 'success', text: '已产出' };
  }

  const latestTask = [...tasks]
    .filter((task) => task.task_name === step)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

  if (latestTask?.status === 'failed') {
    return { tone: 'danger', text: '执行失败' };
  }
  if (latestTask?.status === 'pending' || latestTask?.status === 'running') {
    return { tone: 'accent', text: '执行中' };
  }
  if (isUnlocked(step, snapshot, dependencyMap, selection)) {
    return { tone: 'warn', text: '待处理' };
  }
  return { tone: 'soft', text: '未解锁' };
}

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

const CHINESE_NUMBER_MAP = {
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

function collectProjectListValues(projectInput, keys) {
  return keys
    .flatMap((key) => (Array.isArray(projectInput[key]) ? projectInput[key] : []))
    .map((item) => String(item || '').trim())
    .filter(Boolean);
}

function parseChineseNumber(value) {
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
    if (Object.prototype.hasOwnProperty.call(CHINESE_NUMBER_MAP, char)) {
      current = CHINESE_NUMBER_MAP[char];
    }
  }
  return total + current;
}

function cleanOutlineLine(value) {
  return String(value || '')
    .replace(/^[-•*\s]+/, '')
    .trim();
}

function getGeneratedStructuredPayload(artifact) {
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

function parseOutlineVolumeSections(snapshot) {
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

export function renderInputValue(field, project, snapshot, selection = {}) {
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

export function serializeStepPayload(form, step) {
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

export function getFieldDisplayValue(field, project, snapshot, selection = {}) {
  const enhancedField = { ...field, stepKey: field.stepKey || '' };
  const value = renderInputValue(enhancedField, project, snapshot, selection);
  return field.list ? textFromList(value) : value;
}
