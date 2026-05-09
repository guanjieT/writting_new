# chapter

## 任务

把章节计划写成可直接阅读的小说正文。不是概述，不是提纲，不是策划文案——而是真正的叙事文本。

## 产物定位

这份产物是 revision、consistency、memory 的输入。下游 revision 基于这里的正文做优化；consistency 基于这里的正文检查冲突；memory 基于这里的正文抽取稳定事实。

## 任务核心

1. **场景驱动**：进入场景 -> 冲突或信息交换 -> 状态变化 -> 推向下一场景
2. **冲突持续存在**：每个主要段落都应受目标、阻力、误解、压力、危险、诱惑或代价牵引
3. **人物通过选择表现性格**：不是通过描述，而是通过犹豫、试探、隐瞒、爆发或让步
4. **结尾必须落在 hook 上**：悬念、反转、危险升级、未完成动作，不能平收

## 字数要求

- 正文长度必须以 target_words 为目标
- 至少达到 target_words × 85%
- 宁可略长，不可明显偏短
- 通过扩写场景细节、人物动作、对话博弈、心理反应、环境反馈来增量
- 禁止用重复概述、空泛抒情、总结性段落灌水

## 上下文读取优先级

1. **chapter_plan.structured**：summary、main_event、conflict、hook、scene_summaries、continuity_notes、writing_notes
2. **chapter_plan.structured 完整信息**：title、chapter_type、pov_character、target_words、min_words、characters、introduced_characters
3. **上游产物**：rough_chapter_plan、volume_outline、outline，用于保持一致
4. **step_payload**：用户补充要求，若冲突以 chapter_plan 为准
5. **recent_context_json**：同卷前序章节的正文、修订、一致性检查和记忆摘要，用于保持连续性

## 严格承接

- 必须严格承接 summary、main_event、conflict、hook、scene_summaries、continuity_notes、writing_notes
- 不得擅自改写本章目标、关键冲突、POV、场景顺序、重要设定或关键人物关系
- 不得擅自新增会改变后续规划的大设定、大事件、大反转或关键人物关系
- 如果 scene_summaries 给出了顺序，正文必须按其顺序展开，可以补充过渡、动作和细节，但不能跳过、颠倒或改写场景功能
- continuity_notes 是连续性硬约束，必须落实在正文中
- writing_notes 是写作执行提醒，必须体现在叙事选择里
- 必须读取前序章节上下文，保持人物位置、伤势、情绪余波、信息差、承诺、秘密、物品归属和未解决问题连续
- 不得让人物忘记前序章节刚发生的关键事件；如果有时间跳跃，必须在正文中自然交代状态变化

## 写作硬要求

- 优先通过动作、对白、感官细节、环境压力、心理反应、选择与后果来表现信息
- 少解释，多呈现；少复述设定，多让设定在事件、阻碍、对话潜台词和人物反应中显现
- 每个场景都要让局势发生变化：关系变化、信息变化、目标变化、风险变化、情绪变化或行动方向变化至少有一种
- 对话必须承担推进剧情、暴露动机、制造冲突、遮掩真相、误导信息或改变关系的作用，不能只是空聊天
- 心理描写要贴着当下刺激和人物选择，不要脱离场景长篇说明
- 感官细节要服务气氛、人物状态和冲突压力，不要堆砌无关描写
- 叙事节奏要有张弛：紧张处压缩解释、强化动作和反应；转场处用简洁因果承接

## 防提纲化禁令

- 禁止写"本章主要讲述""这一章中""可以看出""接下来""首先/其次/最后""与此同时，故事推进到"等说明腔
- 禁止把 scene_summaries、continuity_notes、writing_notes 改写成条目或逐项复述
- 禁止用大段旁白替代关键冲突现场；关键事件必须写成正在发生的行动、对白和反应
- 禁止用"他感到很愤怒/她很害怕/局势很紧张"这类抽象判断单独交代情绪；要让表情、动作、语气、身体反应和选择把情绪显出来
- 禁止为了交代设定而让人物说不自然的说明台词
- 禁止把结尾写成总结、安顿或阶段汇报
- 禁止把正文写成"他回想起上一章发生了什么"式的复盘；前序信息要通过当下动作、对白和选择自然体现

## structured 字段

如需要填写 structured，只记录正文产物的简短元信息，不要把正文拆回提纲。例如：

```json
{
  "pov_character": "视角人物",
  "scene_count": 5,
  "word_count_approx": 3200
}
```

## 输出要求

- content：纯文本正文，允许自然分段，禁止放对象、数组、标题列表或提纲
- overview：一两句话概括本章正文实际完成的叙事作用
- key_facts：本章正文中新确定、适合下游继承的事实性条目
- constraints：本章正文确立的后续不能随意改动的边界
- open_questions：本章结束后仍悬而未决、需要后续承接的问题
- best_for_reason：说明这份正文为什么适合给修订、一致性检查和记忆整理继续使用
- structured：可为空对象，如需填写按上述要求

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- chapter_plan_focus_json：当前章节计划结构化重点
- parent_artifact_json：当前章节计划完整上下文
- context_json：当前上下文（step_payload）
- artifacts_json：已有产物摘要（rough_chapter_plan、volume_outline、outline）
- target_words_85：target_words × 85%，用于字数下限检查
- recent_context_json：同卷前序章节上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

当前章节计划结构化重点：
{chapter_plan_focus_json}

当前章节计划完整上下文：
{parent_artifact_json}

当前上下文：
{context_json}

已有产物：
{artifacts_json}

前序章节上下文：
{recent_context_json}

知识库：
{knowledge_base_json}

最低正文长度参考：
{target_words_85}
