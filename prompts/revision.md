# revision

## 任务

做"保留结构功能的正文优化"，不是泛泛润色。不是改写故事，而是针对节奏、表达、冲突强度、叙事连贯性做具体优化。

## 产物定位

这份产物是 consistency 和 memory 的输入。consistency 基于优化后的正文检查冲突；memory 基于优化后的正文抽取稳定事实。

## 任务核心

1. **节奏优化**：紧张场景是否足够压缩？转场是否过于拖沓？每段是否都在推进？
2. **表达优化**：是否有用词不当、表达模糊、冗余重复？对话是否承担了叙事功能？
3. **冲突强度**：关键冲突场景是否足够有力？是否被无关内容稀释？
4. **叙事连贯性**：场景之间是否有因果承接？人物行为是否有内在逻辑？

## 禁止的行为

- 不能改变章节的目标、冲突、hook
- 不能新增或删除重要人物关系
- 不能改变已有的连续性事实
- 不能只换同义词就号称"优化"
- 不能泛泛说"优化表达"而不指出具体改了什么、为什么改

## 输出要求

- content：优化后的正文，允许自然分段
- overview：一两句话说明优化了什么
- key_facts：优化后新确立的事实性条目（如有）
- constraints：已确立的边界，优化后仍需遵守
- open_questions：优化后仍悬而未决的问题
- best_for_reason：说明优化后的正文为什么比原文更适合下游
- structured：优化变更摘要，如 changed_scenes、added_details、removed_redundancy

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- context_json：当前上下文（包含被优化的原文）
- artifacts_json：已有产物（chapter、chapter_plan）

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

当前上下文：
{context_json}

已有产物：
{artifacts_json}

知识库：
{knowledge_base_json}
