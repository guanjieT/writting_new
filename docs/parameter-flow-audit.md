# 参数映射与传递审计

本文记录项目中心字段、步骤表单字段、后端请求字段和生成链路之间的对应关系，便于后续排查“前端填了但生成结果里看不到”的问题。

## 传递链路

1. 项目中心保存长期作品基础设定，数据模型见 [novel_agent/domain.py](../novel_agent/domain.py).
2. 页面进入时，前端通过 `project_id` 从本地存储或 URL 读取当前项目，见 [frontend/assets/js/state.js](../frontend/assets/js/state.js).
3. 项目中心表单提交时，前端把当前输入写回项目对象并调用 `POST /projects` 或 `PUT /projects/{project_id}`，见 [frontend/assets/js/index-page.js](../frontend/assets/js/index-page.js).
4. 步骤页面提交时，前端先把当前表单序列化为 payload，再调用对应后端接口，见 [frontend/assets/js/step-meta.js](../frontend/assets/js/step-meta.js) 和 [frontend/assets/js/workspace-utils.js](../frontend/assets/js/workspace-utils.js).
5. 后端路由接收 payload 后，把它交给 orchestrator 或 AI 补全接口，再由 agent 或 prompt 模板消费，见 [novel_agent/api/routes/workflow_steps.py](../novel_agent/api/routes/workflow_steps.py)、[novel_agent/api/routes/planning.py](../novel_agent/api/routes/planning.py) 与 [novel_agent/infrastructure.py](../novel_agent/infrastructure.py).
6. 生成链路中的上下文组装统一收敛到 [novel_agent/context_builder.py](../novel_agent/context_builder.py)，避免在 agent、路由和模板里重复维护上下文筛选规则。

## 关键字段映射

| 项目中心字段 | 步骤字段 / 目标字段 | 用途 | 说明 |
| --- | --- | --- | --- |
| `title` | `project.input.title` / 多个步骤 prompt | 项目标题 | 所有页面共享 |
| `genre` | `project.input.genre` / 多个步骤 prompt | 题材 | 所有页面共享 |
| `premise` | `requirements.requirements_text` / `project.input.premise` | 一句话前提 | 需求分析页会直接预填 |
| `target_audience` | `requirements.audience` | 需求分析受众 | 需要前端回填到需求页字段 |
| `target_words` | `outline.volume_count`、`chapter.target_words` 等派生字段 | 结构/字数推导 | 前端优先自动回填 |
| `target_volume_count` | `outline.volume_count` | 结构总量 | 前端自动回填 |
| `target_chapters_per_volume` | `outline.chapters_per_volume`、`chapter_plan.target_chapter_count` | 章节密度 | 前端自动回填 |
| `tone` | `story_bible.notes` | 风格与氛围 | 会合并进故事圣经补充说明 |
| `style` | `story_bible.notes` | 风格约束 | 会合并进故事圣经补充说明 |
| `outline_focus` | `outline.focus_points`、`outline.notes`、`characters.notes`、`consistency.known_rules` | 总纲关注点 | 结构页会自动回填 |
| `core_requirements` | `requirements.notes`、`outline.notes`、`volume_outline.notes`、`rough_chapter_plan.notes`、`chapter_plan.notes`、`chapter.notes`、`revision.notes`、`consistency.known_rules`、`memory.notes` | 核心约束 | 会合并进相关步骤的补充说明 |
| `forbidden_elements` | `requirements.notes`、`outline.notes`、`volume_outline.notes`、`rough_chapter_plan.notes`、`chapter_plan.notes`、`chapter.notes`、`revision.notes`、`consistency.known_rules`、`memory.notes` | 禁忌元素 | 会合并进相关步骤的补充说明 |

## 步骤字段与后端字段

### 需求分析

- 前端表单字段：`requirements_text`、`audience`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`RequirementsRequest`
- 路由：`POST /projects/{project_id}/requirements`
- 说明：`requirements_text` 会从项目中心的 `premise` 预填，`audience` 会从 `target_audience` 预填，`notes` 会合并项目约束，所以是最容易看出映射是否正确的地方。

### 世界观生成

- 前端表单字段：`theme`、`world_rules`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`StoryBibleRequest`
- 路由：`POST /projects/{project_id}/story-bible`

### 角色框架

- 前端表单字段：`role_capacity`、`core_roles`、`role_slots`、`role_rules`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`CharacterRequest`
- 路由：`POST /projects/{project_id}/characters`

### 总纲生成

- 前端表单字段：`volume_count`、`chapters_per_volume`、`focus_points`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`OutlineRequest`
- 路由：`POST /projects/{project_id}/outline`
- 说明：`volume_count` 与 `chapters_per_volume` 会优先从项目中心回填，`focus_points` 直接继承 `outline_focus`。

### 卷纲生成

- 前端表单字段：`volume_index`、`volume_title`、`volume_summary`、`volume_goal`、`volume_conflict`、`volume_hook`、`target_words`、`target_chapter_count`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`VolumeOutlineRequest`
- 路由：`POST /projects/{project_id}/volume-outline`
- 说明：`target_words` 和 `target_chapter_count` 也会做项目派生回填；提交时会额外携带 `base_artifact`，并且基底选择以最终提交表单里的 `volume_index` 为准，避免页面级选择器和表单值分叉。

### 粗卷纲

- 前端表单字段：`volume_count`、`chapters_per_volume`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`RoughVolumeOutlineRequest`
- 路由：`POST /projects/{project_id}/rough-volume-outline`
- 说明：这一步只输出全书所有卷的粗纲，不拆成单卷。

### 章节计划

- 前端表单字段：`volume_index`、`chapter_index`、`chapter_title`、`chapter_summary`、`chapter_type`、`pov_character`、`protagonist_present`、`conflict`、`hook`、`target_words`、`min_words`、`characters`、`introduced_characters`、`scene_summaries`、`plan_notes`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`ChapterPlanRequest`
- 路由：`POST /projects/{project_id}/chapter-plan`
- 说明：提交时会额外携带 `base_artifact`，并且基底选择以最终提交表单里的 `volume_index` 和 `chapter_index` 为准，避免页面级选择器和表单值分叉。

### 粗章纲

- 前端表单字段：`volume_index`、`target_chapter_count`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`RoughChapterPlanRequest`
- 路由：`POST /projects/{project_id}/rough-chapter-plan`
- 说明：这一步只输出当前卷所有章节的粗略安排，不拆成单章。

### 章节正文

- 前端表单字段：`volume_index`、`chapter_index`、`chapter_goal`、`target_words`、`scene_beats`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`ChapterRequest`
- 路由：`POST /projects/{project_id}/chapters`

### 修订

- 前端表单字段：`target_artifact`、`instruction`、`focus_areas`、`temperature`、`max_tokens`
- 后端请求模型：`RevisionRequest`
- 路由：`POST /projects/{project_id}/revision`

### 一致性检查

- 前端表单字段：`scope`、`known_rules`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`ConsistencyRequest`
- 路由：`POST /projects/{project_id}/consistency`
- 说明：`known_rules` 会把项目中心的关注点与约束合并进来，减少一致性检查时的上下文丢失。

### 记忆整理

- 前端表单字段：`query`、`top_k`、`notes`、`temperature`、`max_tokens`
- 后端请求模型：`MemoryRequest`
- 路由：`POST /projects/{project_id}/memory`

## AI 补全字段

- 字段级 AI 补全通过 `POST /projects/{project_id}/field-completion` 发送。
- 该接口接收 `step`、`field_key`、`field_label`、`field_type`、`current_value`、`payload`、`temperature`、`max_tokens`。
- 后端会把当前字段、同阶段表单约束和直接上游产物一起组装成补全上下文；例如 `characters.role_capacity=40` 时，`core_roles` 和 `role_slots` 的补全都会明确看到 `role_capacity`。
- 直接上游产物不会原样整段灌进 prompt，而是压缩成结构化摘要视图：`overview`、`key_facts`、`constraints`、`open_questions`、`best_for_steps`，再附少量正文节选，避免长 artifact 淹没字段补全。
- 生成链路按阶段选择上下文：总纲读项目简报和核心上游摘要，卷纲读总纲摘要，章节计划读卷纲摘要与相关设定摘要，章节正文读章节计划摘要和写作约束；字段补全则只读当前字段、同阶段表单约束和直接上游摘要。
- 生成链路现在统一采用单次结构化 payload：模型必须一次返回 `content`、`overview`、`key_facts`、`constraints`、`open_questions`、`best_for_reason`，后端只负责规范化和落库，不再单独做正文后的摘要切分。
- 总纲阶段只产出全书总纲；粗卷纲阶段产出全书所有卷的粗纲；卷纲阶段产出当前卷的完整卷纲；粗章纲阶段产出当前卷的粗章节计划；章节计划阶段产出当前章的完整章节计划。
- 前端实现见 [frontend/assets/js/workspace-utils.js](../frontend/assets/js/workspace-utils.js)。
- 后端实现见 [novel_agent/api/routes/ai.py](../novel_agent/api/routes/ai.py)。

## Artifact 摘要

- 每个 workflow artifact 都会同时保存完整正文和结构化摘要，摘要结构见 [novel_agent/domain.py](../novel_agent/domain.py)。
- 后端生成 artifact 时会要求模型一次返回正文与结构化字段，随后把正文写入 `content`、把结构化字段写入 `summary`；`best_for_steps` 仍由工作流依赖关系补齐，作为明确的依赖提示。
- 工作流 prompt 读取的是 compact artifact context，而不是全文原文；这样既保留可审计的正文，又能让下游步骤优先读到可继承的信息。

## 审计检查点

1. 修改步骤字段时，先确认 [frontend/assets/js/step-meta.js](../frontend/assets/js/step-meta.js) 的字段定义，再确认对应的 `BaseModel`。
2. 如果字段来自项目中心，先检查 `renderInputValue()` 是否做了项目级回填。
3. 如果字段来自当前步骤，先检查 `serializeStepPayload()` 是否把字段纳入 payload。
4. 如果生成结果缺少某个值，先检查 prompt 模板是否真的接到了该字段，而不是直接假设前端没传。
5. 修改映射后，同时更新 [README.md](../README.md) 和本文件，保持可审计。
