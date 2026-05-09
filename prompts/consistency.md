# consistency

## 任务

指出设定冲突、时间线冲突与逻辑漏洞，并给出具体修复建议。不是泛泛说"基本一致"，而是明确指出哪里冲突、证据是什么、影响什么、如何修复。

## 产物定位

这份产物是 memory 和 chapter_plan 的输入。memory 基于这里的冲突点抽取风险提醒；chapter_plan 基于这里的修复建议调整后续章节。

## 任务核心

1. **冲突点必须明确**：哪两个事实之间存在冲突，不能模糊
2. **证据来源必须清晰**：冲突来自哪个 artifact 的哪个字段
3. **影响范围必须具体**：这个冲突会影响哪些后续章节或设定
4. **修复建议必须可执行**：不是"建议检查"，而是具体怎么改
5. **必须对照前序章节上下文**：检查当前章是否遗忘刚发生的状态变化、关系变化、物品归属、伤势、秘密和未解决问题

## structured 关键字段

```json
{
  "conflicts": [
    {
      "conflict_type": "setting/timeline/logic",
      "description": "冲突描述",
      "evidence": [
        {
          "source": "来源 artifact",
          "field": "字段名",
          "value": "具体值"
        }
      ],
      "impact": "影响范围",
      "fix_suggestion": "具体修复建议"
    }
  ]
}
```

## 常见失败模式

1. 写成"整体基本一致，有一些细节可以进一步优化"——没有具体冲突
2. 冲突描述模糊，无法定位
3. 没有证据来源，下游无法核实
4. 修复建议写成"建议进一步检查"——无法执行

## 禁止

- 不要写"需要进一步明确"
- 不要写"整体基本一致"
- 不要写"建议进一步检查"
- 不要写"有一些细节可以优化"
- 不要写泛泛的"注意保持一致"

## 输出要求

- content：纯文本一致性检查报告
- overview：一两句话说明检查范围和主要发现
- key_facts：冲突点、证据来源、影响范围的具体陈述
- constraints：已确立的一致性约束
- open_questions：当前无法确认一致性的问题
- best_for_reason：说明为什么这份一致性报告适合给 memory 和 chapter_plan 使用
- structured：包含 conflicts 数组，每条冲突包含 conflict_type、description、evidence、impact、fix_suggestion

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- context_json：当前上下文
- artifacts_json：已有产物（chapter、chapter_plan、story_bible、characters）
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
