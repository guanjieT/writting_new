# characters

## 任务

生成角色框架。核心角色固定其功能、关系张力、后续生长空间；其余角色以槽位或候选形式表达，不要一次性锁死全部角色。

## 产物定位

这份产物是 outline、volume_outline、rough_chapter_plan 的角色约束来源。outline 生成全书蓝图时必须基于这里的角色关系；rough_chapter_plan 生成章节骨架时必须调度这里的角色。

## 任务核心

1. **区分核心角色与槽位**：核心角色（主角/反派/关键支点）必须明确；其余角色以槽位形式预留
2. **角色必须有功能定位**：不是标签罗列，而是这个角色在故事中承担什么功能
3. **关系必须产生张力**：角色之间的关系要有内在冲突或矛盾，不是和谐的标签组合
4. **生长空间必须可执行**：角色后续要有成长/变化的空间，但不能锁死具体路径

## structured 关键字段

```json
{
  "role_capacity": 8,
  "core_roles": [
    {
      "name": "角色名",
      "function": "在故事中的功能定位",
      "role_type": "protagonist/antagonist/supporting",
      "core_conflict": "角色内在核心冲突",
      "growth_potential": "后续生长方向",
      "key_relationships": ["与其他核心角色的关系"]
    }
  ],
  "role_slots": [
    {
      "slot_type": "槽位类型（如：对手、帮手、情报源）",
      "growth_direction": "这个槽位后续可能演变成什么",
      "flexibility": "是否可替换/合并"
    }
  ],
  "role_rules": ["角色调度规则，如：反派必须在三分之二处才完全亮相"]
}
```

## 常见失败模式

1. 一次性把所有角色都写死，没有生长空间
2. 角色只有标签（"善良""勇敢"），没有功能定位
3. 角色关系和谐，没有张力
4. 角色设定和 world_rules 脱节
5. 角色数量和作品体量不匹配（太多或太少）

## 禁止

- 不要写"需要进一步明确"
- 不要写"后续可补充"
- 不要把角色写成人物小传（出身、爱好、外貌全写）
- 不要把角色关系写成和谐的朋友圈描述
- 不要把非核心角色锁死设计

## 输出要求

- content：纯文本角色框架正文，描述核心角色功能、关系张力、槽位设计
- overview：一两句话说明这份角色框架的作用
- key_facts：核心角色功能、关系张力、角色调度规则的具体陈述
- constraints：已确立的角色边界，下游必须遵守
- open_questions：当前未确定但影响后续展开的角色问题
- best_for_reason：说明为什么这份角色框架适合给 outline、rough_chapter_plan 使用
- structured：包含 role_capacity、core_roles、role_slots、role_rules

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- input_json：完整项目输入（参考 outline_focus、core_requirements、forbidden_elements）
- character_frame_json：角色框架输入（如果有）
- artifacts_json：已有产物（requirements、story_bible）
- context_json：当前步骤上下文

## 实际输入上下文

项目概述：
{project_summary}

项目简报：
{project_brief_json}

完整项目输入：
{input_json}

角色框架输入：
{character_frame_json}

已有产物：
{artifacts_json}

当前步骤上下文：
{context_json}

知识库：
{knowledge_base_json}
