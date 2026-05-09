# rough_chapter_plan

## 任务

生成当前卷所有章节的粗略章节计划。不是章级细节，而是能给 chapter_plan 提供骨架的章节职能分配。

## 产物定位

这份产物是 chapter_plan 的输入蓝图。chapter_plan 基于这里的每章 main_event、conflict、hook 来展开 scene_summaries。

## 任务核心

1. **每章必须有不同推进职能**：不是"承上启下"，而是具体承担什么推进功能
2. **main_event 必须具体**：不是"发生了一些事"，而是明确的核心事件
3. **conflict 必须有焦点**：不是泛泛的"有冲突"，而是本章冲突的焦点是什么
4. **hook 必须可下钻**：不是"留下悬念"，而是明确的信息缺口或事件

## structured 关键字段

```json

```

## 常见失败模式

1. 每章的 summary 都是"承上启下"——同质化
2. main_event 写成"推进剧情"——没有具体事件
3. conflict 写成"有冲突"——没有焦点
4. hook 写成"留下悬念"——无法下钻
5. 章节之间没有递进关系

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把章节写成"第1章：开始、第2章：继续"
- 不要把 main_event 写成"发生了一些事"
- 不要把 hook 写成"请看下章"

## 输出要求

- content：纯文本整卷章节骨架摘要，说明章节之间的推进关系
- overview：一两句话说明这份粗章纲的作用
- key_facts：每章 main_event、conflict、hook 的具体陈述
- constraints：已确立的章节边界，下游必须遵守
- open_questions：当前未确定但影响章节展开的问题
- best_for_reason：说明为什么这份粗章纲适合给 chapter_plan 使用
- structured：包含 volume_index、total_target_chapters、chapters 数组，每章包含 chapter_index、title、summary、chapter_type、pov_character、main_event、conflict、hook、target_words

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入
- parent_artifact_json：前置卷纲摘要（volume_outline 的 structured）
- step_payload_json：步骤输入（包含 volume_index）
- artifacts_json：已有产物（outline、volume_outline、rough_volume_outline）
- context_json：当前步骤上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

前置卷纲：
{parent_artifact_json}

步骤输入：
{step_payload_json}

已有产物：
{artifacts_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
