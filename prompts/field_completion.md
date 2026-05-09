# field_completion

## 任务

补全当前字段，不是重写整个表单。只补当前字段，不动其他字段；优先利用上游 structured 信息，不要只看自然语言摘要。

## 产物定位

这份产物直接回填到表单的当前字段。不是生成新内容，而是根据上下文补全用户可能遗漏的信息。

## 核心原则

### 1. 只补当前字段
- 不重写整个表单
- 不替用户做决定
- 不修改其他字段

### 2. 证据优先级
1. reference_fields（字段上下文中的关键字段）
2. direct_dependency_artifacts（直接上游产物的 structured）
3. project_input（项目输入）

### 3. 保守补全
- 没有足够依据时，不要乱发明
- 当前值已经可用时，只微调，不大改
- 不要和已有项目约束冲突
- 不要引入上游没有的新设定

### 4. 按字段类型输出
- number：只输出数字，如 `3000`
- checkbox：只输出 `true` 或 `false`
- title：短、可用、不要矫饰，如 `"第一章：初入江湖"`
- list textarea：一行一条，少废话
- short text：短、准、可粘贴
- summary/notes：允许略展开，但必须贴字段用途，不要发散

### 5. 质量要求
- 直接可回填
- 和字段目的匹配
- 和上游一致
- 无解释
- 无前后缀
- 不空泛

## 禁止

- 不要输出"根据上下文，建议..."
- 不要输出"当前值已足够，无需修改"
- 不要输出任何解释性文字
- 不要在数字字段输出"约"或"大约"
- 不要在标题字段输出"第X章：标题"以外的装饰
- 不要输出空值时假装有内容

## 输出要求

直接输出字段内容，不要有任何前后缀。示例：
- 数字字段：`3000`
- 复选框字段：`true`
- 标题字段：`初入江湖`
- 列表字段：
  ```
  角色A：关键盟友，在第3章后成为核心支持
  角色B：对手，意图不明，在第5章揭示真实目的
  ```
- 摘要字段：
  ```
  本卷核心目标：主角完成第一次重大抉择
  主要冲突：与反派A的第一次正面交锋
  卷尾悬念：主角发现自己的真实身世
  ```

## 输入变量

- project_summary：项目概述
- project_brief_json：项目简报
- step_label：当前步骤名称
- step_description：当前步骤说明
- field_label：当前字段标签
- field_type：当前字段类型
- field_placeholder：当前字段提示
- current_value：当前值（可能为空）
- field_context_json：字段上下文（包含 key、label、type、placeholder、current_value）
- reference_fields_json：关键字段上下文（包含 purpose、focus、output_mode、project_fields、step_fields）
- step_payload_json：同阶段表单（当前字段已移除）
- direct_dependency_steps_json：直接上游步骤列表
- direct_dependency_artifacts_json：直接上游产物
- input_json：项目输入