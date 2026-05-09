# outline

## 任务

生成全书总纲。不是简介，不是简介，不是简介——而是能给 rough_volume_outline 提供真正可执行的全书蓝图。

## 产物定位

这份产物是 rough_volume_outline 的输入蓝图。rough_volume_outline 基于这里的三段式结构来分卷；volume_outline 基于这里的卷级目标来生成卷纲；chapter 基于这里的全书主线来确保章节不偏离。

## 任务核心

1. **全书目标必须清晰**：读者在最后一章看到什么？主角完成什么？主题如何收束？
2. **阶段推进必须有递进**：三段式不是机械划分，而是冲突不断升级、代价不断加大的过程
3. **冲突升级必须有路径**：从头到尾冲突如何演变，不能只是"越来越激烈"
4. **结局方向必须有约束**：结局是类型决定的还是人物弧线决定的，要说清楚

## structured 关键字段

```json
{
  "story_arcs": [
    {
      "arc_index": 1,
      "title": "弧线名称",
      "summary": "弧线摘要",
      "starting_state": "起始状态",
      "ending_state": "结束状态",
      "key_turning_points": ["关键转折点"]
    }
  ],
  "global_goals": ["全书目标"],
  "main_conflicts": [
    {
      "conflict": "冲突描述",
      "escalation_path": "冲突如何升级"
    }
  ],
  "ending_direction": "结局方向与约束",
  "volume_plan_hints": [
    {
      "volume_index": 1,
      "hint": "第1卷承担什么功能"
    }
  ]
}
```

## 常见失败模式

1. 三段式写成"第一部分：开头；第二部分：中间；第三部分：结尾"——没有实质内容
2. 全书目标写成"主角成长"这种空泛概念——任何内容都算成长
3. 冲突升级没有路径，只是"越来越激烈"
4. volume_plan_hints 写成完整卷纲，而不是提示

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把三段式写成三句话简介
- 不要把 volume_plan_hints 写成完整卷纲
- 不要把全书目标写成"讲一个好故事"

## 输出要求

- content：纯文本全书总纲正文，包含全书目标、阶段推进、冲突升级、结局方向
- overview：一两句话说明这份总纲的作用
- key_facts：三段式结构、冲突升级路径、结局方向约束的具体陈述
- constraints：已确立的全书边界，下游必须遵守
- open_questions：当前未确定但影响后续卷级展开的问题
- best_for_reason：说明为什么这份总纲适合给 rough_volume_outline、volume_outline、chapter 使用
- structured：包含 story_arcs、global_goals、main_conflicts、ending_direction、volume_plan_hints

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入
- outline_targets_json：总纲目标参数（如果有）
- step_payload_json：步骤输入
- artifacts_json：已有产物（requirements、story_bible、characters）
- context_json：当前步骤上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

总纲目标参数：
{outline_targets_json}

步骤输入：
{step_payload_json}

已有产物：
{artifacts_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
