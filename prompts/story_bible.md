# story_bible

## 任务

生成能真正约束剧情与人物的世界规则。不是装饰性设定罗列，而是包含代价、边界、冲突源的可执行规则。

## 产物定位

这份产物是 characters、outline、volume_outline 的约束来源。characters 生成角色时必须符合这里的世界规则；outline 生成全书蓝图时必须基于这里的冲突结构；volume_outline 生成卷纲时必须承接这里的规则约束。

## 任务核心

1. **规则必须有代价**：每条世界规则都要有后果——不是什么都能做，做了有代价
2. **冲突必须有来源**：核心冲突来自世界本身的矛盾，不是外加的
3. **边界必须可执行**：规则必须能约束下游创作，不是模糊方向
4. **可持续展开**：规则要有内在张力，能推动故事持续展开

## structured 关键字段

```json
{
  "theme": "核心主题，一句话",
  "world_rules": [
    {
      "rule": "规则名称",
      "description": "具体描述",
      "cost": "违反或使用此规则的代价",
      "conflict_source": "此规则如何产生冲突"
    }
  ],
  "power_system": "能力体系描述（如果有）",
  "social_structure": "社会结构与运行逻辑",
  "key_settings": ["核心场景/地点"],
  "main_conflicts": ["主要冲突来源"]
}
```

## 常见失败模式

1. 世界规则只有装饰性描述，没有代价和后果
2. 设定名词罗列，不产生冲突
3. 世界观和故事脱节，设定存在但不影响人物行动
4. 规则太宽松，什么都能做，没有边界
5. 规则太死，没有展开空间

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把世界规则写成旅游手册式的地点描述
- 不要把能力体系写成游戏技能表
- 不要写只有名词没有冲突的设定

## 输出要求

- content：纯文本世界观正文，描述核心规则与冲突结构
- overview：一两句话说明这份世界规则的作用
- key_facts：规则、代价、边界、冲突源的具体陈述
- constraints：已确立的世界规则边界，下游必须遵守
- open_questions：当前未确定但影响后续展开的问题
- best_for_reason：说明为什么这份世界规则适合给 characters、outline、volume_outline 使用
- structured：包含 theme、world_rules、power_system、social_structure、key_settings、main_conflicts

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入（参考 premise、genre、tone、core_requirements、forbidden_elements）
- artifacts_json：已有产物（requirements）
- context_json：当前步骤上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

已有产物：
{artifacts_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
