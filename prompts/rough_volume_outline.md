# rough_volume_outline

## 任务

生成全书所有卷的粗略纲要。不是完整卷纲，而是能指导 volume_outline 生成的卷级蓝图。

## 产物定位

这份产物是 volume_outline 的输入蓝图。volume_outline 基于这里的卷目标、卷冲突、卷尾钩子来生成完整卷纲；rough_chapter_plan 基于这里的卷结构来分配章节。

## 任务核心

1. **每卷必须有独立目标**：不是"推进剧情"，而是本卷要完成什么具体阶段任务
2. **卷与卷之间必须有因果推进**：第N卷的结果如何推动第N+1卷，不是机械并列
3. **冲突必须升级**：每卷的冲突要比上一卷更激烈或更深层
4. **卷尾钩子必须具体可承接**：不是模糊悬念，而是明确的信息缺口或事件

## structured 关键字段

```json
{
  "volumes": [
    {
      "volume_index": 1,
      "title": "第1卷标题",
      "summary": "1~2句卷摘要",
      "goal": "本卷要完成的阶段任务",
      "main_conflict": "本卷核心冲突",
      "ending_hook": "卷尾悬念或信息缺口",
      "target_chapter_count": 12,
      "target_words": 25000
    }
  ]
}
```

## 常见失败模式

1. 卷与卷之间没有因果推进，只是"故事继续"
2. 每卷的 goal 都是"推进剧情"——没有独立目标
3. 卷尾钩子写成"欲知后事如何请看下回"——没有具体信息缺口
4. 卷的冲突没有升级，只是换了场景
5. 卷平均分配篇幅，没有节奏差异

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把卷写成"第1卷：开始、第2卷：中间、第3卷：结尾"
- 不要把卷尾钩子写成"这一卷结束了"这种废话
- 不要平均分配卷的章节数或字数（可以有差异）

## 输出要求

- content：纯文本全书卷级规划摘要，说明卷与卷之间的关系和升级
- overview：一两句话说明这份粗卷纲的作用
- key_facts：卷目标、卷冲突、卷尾钩子、卷间因果的具体陈述
- constraints：已确立的卷级边界，下游必须遵守
- open_questions：当前未确定但影响后续章节展开的问题
- best_for_reason：说明为什么这份粗卷纲适合给 volume_outline、rough_chapter_plan 使用
- structured：包含 volumes 数组，每卷包含 volume_index、title、summary、goal、main_conflict、ending_hook、target_chapter_count、target_words

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入
- outline_targets_json：总纲目标参数
- step_payload_json：步骤输入
- artifacts_json：已有产物（outline）
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
