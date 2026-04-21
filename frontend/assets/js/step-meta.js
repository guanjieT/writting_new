import { api } from './api-client.js';

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
