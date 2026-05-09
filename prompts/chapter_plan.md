# chapter_plan

## 任务

生成当前章的完整章节计划。不是概述，不是提纲，而是可直接指导 chapter 生成正文写作的执行方案。

## 产物定位

这份产物是 chapter 的输入蓝图。chapter 基于这里的 scene_summaries、continuity_notes、writing_notes 来生成正文。

## 任务核心

1. **scene_summaries 必须可执行**：每个场景都有明确的进入条件、事件推进、退出条件
2. **continuity_notes 是硬约束**：前面章节确立的事实、关系、状态，必须在本文中保持一致
3. **writing_notes 是执行提醒**：这一章有什么特殊写作要求、注意事项
4. **章节必须有独特价值**：不是"承接上文"，而是这一章本身完成了什么叙事功能

## structured 关键字段

```json
{
  "volume_index": 1,
  "chapter_index": 1,
  "title": "第1章标题",
  "summary": "章节摘要",
  "chapter_type": "主线推进章/冲突章/过渡章/爆点章",
  "pov_character": "视角人物",
  "main_event": "本章核心推进事件",
  "conflict": "本章冲突焦点",
  "hook": "本章结尾钩子",
  "target_words": 3000,
  "min_words": 2500,
  "characters": ["本章出场人物"],
  "introduced_characters": ["本章新登场人物"],
  "scene_summaries": [
    {
      "scene_index": 1,
      "setting": "场景地点/时间",
      "summary": "场景事件",
      "function": "这个场景在章内的功能"
    }
  ],
  "continuity_notes": ["前面章节确立的事实，本章必须保持一致"],
  "writing_notes": ["本章特殊写作要求或注意事项"]
}
```

## 常见失败模式

1. scene_summaries 写成抽象摘要，没有场景进入/退出条件
2. continuity_notes 缺失或太模糊，无法约束正文写作
3. writing_notes 太笼统，没有具体执行提醒
4. 每章的 chapter_type 都是"主线推进章"——同质化
5. hook 写成"请看下章"——没有明确的信息缺口

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把 scene_summaries 写成"场景1：发生了一件事"
- 不要把 continuity_notes 写成"注意保持一致"这种无法执行的废话
- 不要把 writing_notes 写成"注意写作质量"这种空洞提醒

## 连续性要求

- 必须读取 recent_context_json，继承前序章节已经确立的事实、关系状态、伤势、物品归属、承诺、秘密和未解决问题。
- continuity_notes 必须写成可执行的连续性约束，不能只写"注意承接前文"。
- 如果当前章需要回收或延续前序章节的 open_questions，必须在 scene_summaries 或 writing_notes 中明确安排。

## 输出要求

- content：纯文本当前章摘要，不是 scene_summaries 的复述
- overview：一两句话说明这份章节计划的作用
- key_facts：scene_summaries、continuity_notes、writing_notes 的具体陈述
- constraints：已确立的章节边界，下游必须遵守
- open_questions：当前未确定但影响正文写作的问题
- best_for_reason：说明为什么这份章节计划适合给 chapter 使用
- structured：包含上述所有字段

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入
- parent_artifact_json：前置粗章纲摘要（rough_chapter_plan 的 structured）
- step_payload_json：步骤输入（包含 volume_index、chapter_index）
- artifacts_json：已有产物（volume_outline、outline、rough_chapter_plan）
- context_json：当前步骤上下文
- recent_context_json：同卷前序章节的正文、修订、一致性检查和记忆摘要

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

前置粗章纲：
{parent_artifact_json}

步骤输入：
{step_payload_json}

已有产物：
{artifacts_json}

前序章节上下文：
{recent_context_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
