# volume_outline

## 任务

生成当前卷的完整卷纲。不是总纲语言，不是章级细节，而是能指导 rough_chapter_plan 生成的卷级作战图。

## 产物定位

这份产物是 rough_chapter_plan 的输入蓝图。rough_chapter_plan 基于这里的 arc_segments 来设计章节；chapter 基于这里的卷目标来确保章节不偏离。

## 任务核心

1. **卷目标必须具体可执行**：本卷完成什么阶段任务，不是总纲的重复
2. **卷冲突必须有内在结构**：不是一句话冲突，而是有起承转合的冲突弧
3. **arc_segments 必须可操作**：卷内如何分阶段推进，每个阶段承担什么功能
4. **卷尾钩子必须有明确的信息缺口或事件**：不是模糊悬念

## structured 关键字段

```json
{
  "volume_index": 1,
  "title": "第1卷标题",
  "summary": "卷摘要",
  "goal": "本卷阶段任务",
  "main_conflict": "本卷核心冲突",
  "ending_hook": "卷尾信息缺口或事件",
  "target_chapter_count": 12,
  "target_words": 25000,
  "arc_segments": [
    {
      "segment_index": 1,
      "summary": "阶段摘要",
      "chapters_covered": "覆盖章数",
      "function": "这个阶段在卷内的功能"
    }
  ]
}
```

## 常见失败模式

1. 卷纲写成总纲的微缩版——语言还是全书视角
2. arc_segments 太抽象，看不出具体怎么推进
3. 卷尾钩子写成"这一卷结束了"——没有信息缺口
4. 卷内没有独立的起承转合，只是"不断推进"

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把卷纲写成总纲的缩句
- 不要把 arc_segments 写成"前期/中期/后期"这种空泛划分
- 不要把卷尾钩子写成"第N+1卷继续"这种废话

## 输出要求

- content：纯文本当前卷摘要，不是全文复述
- overview：一两句话说明这份卷纲的作用
- key_facts：卷目标、卷冲突、arc_segments、卷尾钩子的具体陈述
- constraints：已确立的卷级边界，下游必须遵守
- open_questions：当前未确定但影响后续章节展开的问题
- best_for_reason：说明为什么这份卷纲适合给 rough_chapter_plan、chapter 使用
- structured：包含 volume_index、title、summary、goal、main_conflict、ending_hook、target_chapter_count、target_words、arc_segments

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入
- parent_artifact_json：前置粗卷纲摘要（rough_volume_outline 的 structured）
- step_payload_json：步骤输入（包含 volume_index）
- artifacts_json：已有产物（outline、rough_volume_outline）
- context_json：当前步骤上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

前置粗卷纲：
{parent_artifact_json}

步骤输入：
{step_payload_json}

已有产物：
{artifacts_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
