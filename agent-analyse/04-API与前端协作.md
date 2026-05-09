# API 与前端协作

## API 结构

FastAPI 应用在 `api/app.py` 中组装。主要路由包括：

| 路由文件 | 职责 |
| --- | --- |
| `routes/frontend.py` | 返回多页面 HTML |
| `routes/health.py` | 健康检查 |
| `routes/workflow.py` | 返回工作流规范 |
| `routes/projects.py` | 项目 CRUD、快照、删除 artifact |
| `routes/workflow_steps.py` | 基础工作流步骤和任务查询 |
| `routes/planning.py` | 卷纲、粗章纲、章节计划等结构步骤 |
| `routes/ai.py` | 字段级 AI 补全 |

请求体模型集中在 `api/schemas.py`。前端每个步骤字段都应该能在这里找到对应请求模型，否则就会出现“前端填了但后端吃不到”的问题。

## 生成接口模式

多数生成接口都遵循同一个模式：

```text
POST /projects/{project_id}/{step-endpoint}
  -> 创建 TaskRecord
  -> 后台执行 orchestrator.dispatch(...)
  -> 立即返回 task
```

前端拿到 `task_id` 后调用：

```text
GET /tasks/{task_id}
```

直到任务状态变为 `completed` 或 `failed`。

这个异步设计的好处是接口不会因为 LLM 慢而卡死浏览器，也方便前端展示执行中、失败和任务历史。

## 项目接口

项目中心主要使用：

- `POST /projects`：创建项目。
- `PUT /projects/{project_id}`：更新项目基础设定。
- `GET /projects`：列出项目。
- `GET /projects/{project_id}`：获取项目。
- `GET /projects/{project_id}/snapshot`：获取项目和 artifacts 的完整快照。
- `GET /projects/{project_id}/quality-report`：获取基础质量门禁报告。
- `GET /projects/{project_id}/exports/manuscript`：按卷章导出 Markdown 成稿。
- `DELETE /projects/{project_id}`：删除项目。
- `DELETE /projects/{project_id}/artifacts/{artifact_key}`：删除某个 artifact 及其后代。

更新项目时后端会清空旧 artifacts 和旧任务，因为基础设定变化后，已有产物已经不可信。

## 前端 API 封装

`frontend/assets/js/api-client.js` 是前端所有 HTTP 调用的统一入口。它负责：

- 统一 JSON 请求。
- 读取错误响应。
- 暴露 `api.runRequirements()`、`api.runOutline()` 等步骤函数。
- 提供 `waitForTask()` 轮询任务结果。

其他前端模块不直接写 fetch 细节，而是调用这里的 API 方法。

## 步骤元数据

`step-meta.js` 是前端工作流 UI 的核心表。

每个步骤包含：

- 页面归属。
- 展示名称。
- 描述文案。
- 表单字段。
- 审查清单。
- 对应 endpoint。

例如 `chapter_plan` 的字段里有 `volume_index`、`chapter_index`、`chapter_title`、`chapter_summary`、`scene_summaries` 等，提交时会被 `workspace-utils.js` 序列化为 payload，然后发给 `api.runChapterPlan()`。

这个文件是前端和后端 schema 最容易不一致的地方。修改字段时必须同时确认：

1. `step-meta.js` 的字段存在。
2. `workspace-utils.js` 能正确序列化。
3. `api/schemas.py` 有对应请求字段。
4. Prompt 模板确实使用了该字段。

## 多页面协作

前端并不是单页应用，而是多 HTML 页面共享 JS 模块。

页面之间通过两种方式保持上下文：

- URL query：`project_id`、`volume_index`、`chapter_index`。
- localStorage：当前选中项目 ID。

`state.js` 负责项目 ID 的读取、保存和导航链接同步。`scope-utils.js` 负责卷章选择归一化。

## 工作区通用逻辑

`workspace-utils.js` 是多个页面复用最多的模块。它负责：

- 渲染表单字段。
- 序列化表单。
- 构造字段级 AI 补全请求。
- 执行步骤并等待任务完成。
- 构造 `base_artifact`。
- 展示 artifact 摘要、正文和 metadata。
- 删除当前步骤 artifact。

其中 `buildBaseArtifactPayload()` 很关键。对于部分步骤，前端会显式把当前父级 artifact 附进 payload：

- `volume_outline` 附 `rough_volume_outline`。
- `chapter_plan` 附当前卷的 `rough_chapter_plan`。
- `chapter` 附当前章的 `chapter_plan`。

后端 `PlanningAgent` 会优先使用这个 `base_artifact`，没有时再从项目 artifacts 中按作用域查找。

## 前端依赖状态

`artifact-selectors.js` 负责判断一个步骤是否可执行。

它会按当前选择的卷章查找依赖 artifact，并判断：

- 缺失：按钮不可用。
- stale：按钮不可用并提示前置已失效。
- active：可以执行。

这套判断和后端 `_ensure_step_ready()` 是对应关系。前端判断用于用户体验，后端判断用于最终安全校验。即使前端误判，后端仍会阻止非法执行。

## 前端引导

主工作流侧栏会根据当前项目快照、任务状态和步骤依赖计算“建议下一步”。它优先暴露失败任务，其次暴露当前上下文中已经解锁但还没有产物的对象。这样用户不需要先理解完整依赖图，也能沿着推荐项推进。

主工作流页面现在按“创作驾驶舱”组织信息：

- 左侧先展示项目摘要、阶段进度条、建议下一步和当前卷章范围，再展示完整步骤列表。
- 阶段进度条按设定、结构、写作、审查分组，统计当前项目和当前卷章范围下的产物完成数。
- 主工作区在表单前展示“读取 / 产出 / 范围 / 影响”，把当前步骤和上下游产物关系说清楚。
- 生成按钮会根据当前范围是否已有 artifact 显示“生成对象名”或“重新生成对象名”，避免用户误以为所有步骤只是同一种后台任务。

审查台会读取质量报告和项目进度，展示正文完成数、质量阻塞数和导出状态。质量报告来自 `GET /projects/{project_id}/quality-report`。

## 字段级 AI 补全

字段补全接口是：

```text
POST /projects/{project_id}/field-completion
```

前端发送当前字段、当前表单 payload、字段类型、已有值、温度和最大 tokens。后端使用 `build_completion_context()` 组装：

- 当前字段信息。
- 当前步骤其他字段。
- 与该字段相关的项目设定。
- 直接上游 artifacts 的压缩摘要。

补全结果只返回一个 `suggestion` 字符串，然后前端回填到对应控件。

这个功能的设计目标是“局部补参数”，而不是重跑整个步骤。
