# memory

## 任务

抽取稳定设定、未决问题与后续写作提醒。不是泛泛摘要，而是下游可直接拿来使用的稳定事实和风险提醒。

## 产物定位

这份产物是 chapter 和 chapter_plan 的输入。chapter 基于这里的稳定设定写作；chapter_plan 基于这里的未决问题设计钩子。

## 任务核心

1. **稳定设定必须可直接使用**：不是"世界观是XX"，而是"角色A和角色B的关系是XX，当前处于XX状态"
2. **未决问题必须具体**：不是"故事有很多悬念"，而是"角色A的真实身份在第3章后未揭示，预计在第8章揭示"
3. **写作风险必须可执行**：不是"注意写作质量"，而是"角色A在愤怒时容易失控，后续章节在设计冲突时要注意这一点"

## structured 关键字段

```json
{
  "stable_facts": [
    {
      "fact": "稳定事实描述",
      "source": "来源章节或 artifact",
      "confidence": "high/medium"
    }
  ],
  "unresolved_questions": [
    {
      "question": "未决问题描述",
      "expected_resolution": "预期解决时机",
      "stakes": "如果未解决会影响什么"
    }
  ],
  "writing_risks": [
    {
      "risk": "风险描述",
      "affected_characters": ["受影响角色"],
      "mitigation": "如何规避"
    }
  ],
  "upcoming_reminders": [
    {
      "reminder": "提醒内容",
      "trigger_at": "触发时机"
    }
  ]
}
```

## 常见失败模式

1. 写成"第1章发生了XX，第2章发生了XX"——编年史，不是稳定事实
2. 未决问题写成"有很多悬念待解决"——无法执行
3. 写作风险写成"注意写作质量"——空洞
4. upcoming_reminders 写成"后续注意"——没有具体触发时机

## 长篇记忆要求

- stable_facts 只记录后续必须稳定继承的事实，不记录一次性的场景流水账。
- unresolved_questions 必须写清楚触发条件和后续需要在哪类场景承接。
- writing_risks 必须指出容易写错的连续性风险。
- upcoming_reminders 必须能直接服务下一章或后续几章写作。

## 禁止

- 不要写"需要进一步明确"
- 不要写"整体记忆良好"
- 不要写成章节目录式的摘要
- 不要把时间线当成稳定事实（时间线可能变化）
- 不要写无法执行的空洞提醒

## 输出要求

- content：纯文本记忆整理报告
- overview：一两句话说明这份记忆整理的作用
- key_facts：稳定设定、未决问题、写作风险的具体陈述
- constraints：已确立的约束
- open_questions：当前无法确定的问题
- best_for_reason：说明为什么这份记忆整理适合给 chapter 和 chapter_plan 使用
- structured：包含 stable_facts、unresolved_questions、writing_risks、upcoming_reminders

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- context_json：当前上下文
- artifacts_json：已有产物（chapter、revision、consistency）
- recent_context_json：同卷前序章节上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

当前上下文：
{context_json}

已有产物：
{artifacts_json}

前序章节上下文：
{recent_context_json}

知识库：
{knowledge_base_json}
