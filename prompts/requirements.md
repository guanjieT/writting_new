# requirements

## 任务

生成小说需求文档。目标是让 story_bible、characters、outline 能够直接继承这些约束，无需二次确认。

## 产物定位

这份产物是所有后续步骤的输入约束来源。story_bible 生成世界观规则时必须遵守这里的受众定位和禁忌边界；characters 生成角色时必须遵守这里的作品目标；outline 生成全书蓝图时必须遵守这里的体量和风格约束。

## 任务核心

1. **受众定位**：不是模糊的"年轻女性读者"，而是具体画像——年龄、阅读习惯、情感需求、期待类型
2. **作品目标**：不是"讲一个有趣的故事"，而是具体要完成什么叙事功能、情绪弧线、主题表达
3. **体量边界**：卷数、每卷章数、总字数目标，必须让 outline 能直接据此拆解
4. **禁忌边界**：哪些绝对不能写、哪些绝对不能出现，必须具体到下游能直接执行

## structured 关键字段

```json
{
  "title": "书名",
  "genre": "题材",
  "premise": "一句话前提",
  "target_words": 80000,
  "target_volume_count": 3,
  "target_chapters_per_volume": 12,
  "target_audience": "具体受众画像，不是泛泛描述",
  "tone": ["情感基调和叙事风格"],
  "style": ["语言风格要求"],
  "outline_focus": ["全书重点关注点"],
  "core_requirements": ["必须满足的核心要求"],
  "forbidden_elements": ["绝对禁止出现的元素"]
}
```

## 常见失败模式

1. 受众写成"适合所有读者"——无法约束任何创作决策
2. 作品目标写成"讲一个好故事"——任何输出都算"好故事"
3. 禁忌写成"敏感内容注意"——下游无法执行
4. core_requirements 和 forbidden_elements 不够具体，导致 outline 可以自行其是

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要写"视情况调整"
- 不要把受众写成"适合XX读者"这种宽泛描述
- 不要把禁忌写成"注意不要写敏感内容"这种无法执行的废话

## 输出要求

- content：纯文本需求正文，可以分段
- overview：一两句话说明这份需求文档的作用
- key_facts：受众定位、作品目标、体量约束、禁忌边界的具体陈述
- constraints：已确立的边界，下游必须遵守
- open_questions：当前无法确定但下游需要关注的问题
- best_for_reason：说明为什么这份文档适合给 story_bible、characters、outline 使用
- structured：包含上述所有字段的具体值

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报（包含 title、genre、premise、target_words 等）
- input_json：完整项目输入
- context_json：当前步骤上下文（step_payload）

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
