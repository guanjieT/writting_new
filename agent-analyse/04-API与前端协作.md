# GUI 架构与后端协作

## 概述

前端已从 Web（FastAPI + HTML/JS）迁移为 Python tkinter 桌面 GUI。`novel_agent/api/` 和 `frontend/` 目录已删除。GUI 直接通过 `AppContainer` 调用后端服务，无 HTTP 层。

## GUI 结构

GUI 包位于 `novel_agent/gui/`，采用单窗口多视图架构。

| 文件 | 职责 |
| --- | --- |
| `__main__.py` | 入口：`python -m novel_agent.gui` |
| `app.py` | Tk 根窗口、DI 容器初始化、侧栏导航、视图切换、范围选择 |
| `state.py` | `AppShared` 共享状态数据类 |
| `theme.py` | 统一管理 GUI 色彩、字体、ttk 样式和原生控件样式工具 |
| `step_fields.py` | 12 个工作流步骤的字段定义（Python 版 step-meta.js） |
| `scope_utils.py` | 范围解析、产物查找、结构化数据解析、依赖检查、默认值回填 |
| `task_monitor.py` | tkinter.after() 异步任务轮询 |
| `widgets/form_builder.py` | 动态表单构建：FieldDef → tkinter 控件 |
| `widgets/artifact_viewer.py` | 产物只读展示（内容、摘要、结构化数据、元数据） |
| `views/project_view.py` | 项目中心：创建、列出、编辑、删除项目 |
| `views/workflow_view.py` | 主工作台：步骤导航、动态表单、产物查看、依赖检查 |
| `views/review_view.py` | 审查面板：总览统计、进度矩阵、任务历史、质量报告 |

## 数据流

GUI 调用后端服务是直接 Python 函数调用：

```
用户点击"生成"
  → form_builder.read_payload() → dict
  → task_service.submit(job=lambda: orchestrator.dispatch(...))
  → task_monitor.start_polling(task_id)  # tkinter.after() 轮询
  → on_complete: 刷新快照，重新渲染视图
```

所有调用路径：`container.orchestrator.dispatch(...)`、`container.project_service.create(...)`、`container.task_service.list(...)` 等。

## 异步处理

- **任务轮询**：`TaskMonitor` 使用 `root.after(1200, ...)` 检查任务状态。非阻塞，GUI 保持响应。
- **字段 AI 补全**：在 `threading.Thread(daemon=True)` 中运行，结果通过 `root.after(0, callback)` 回传主线程。

## 范围选择

侧栏中的卷/章 Combobox。值从结构化产物数据填充（从 `rough_volume_outline` 和 `rough_chapter_plan` 解析）。切换选择时刷新当前视图。

项目级步骤不使用范围选择。卷级步骤使用 volume_index。章级步骤同时使用 volume_index 和 chapter_index。

## 步骤字段定义

`step_fields.py` 是 `step-meta.js` 的 Python 移植。每个步骤有 `label`、`group`、`description`、`review_points` 和 `fields: list[FieldDef]`。字段类型：`text`、`textarea`、`number`、`select`、`checkbox`、`list`。Select 选项从快照数据动态解析。

`widgets/form_builder.py` 负责把字段值读成后端可消费的 payload。下拉框显示 label，但提交时会通过 `_value_map` 转回 option value；程序化回填时也会把 value 反查成 label，以保证 GUI 展示和后端参数一致。

## 视觉主题

GUI 统一通过 `theme.apply_theme(root)` 应用主题：

- 主壳使用深色侧栏承载品牌、导航、当前项目和范围选择。
- 内容区使用浅色工作台风格，项目中心、工作台、审查面板共享标题、按钮、列表、表格和输入控件样式。
- `style_text_widget()` 和 `style_listbox()` 专门处理 tkinter 原生控件，弥补 ttk 主题无法覆盖 `Text`、`Listbox` 的问题。
- 页面文件只引用共享样式和主题色，不再各自维护分散的颜色常量。

## 视图协作

三个视图共享 `AppShared` 状态对象：

- `current_project_id`：当前选择的项目
- `current_snapshot`：完整的项目快照（项目数据、产物、知识库、进度）
- `current_tasks`：任务记录列表
- `scope`：当前卷/章选择

视图切换由 `App.switch_view()` 处理，每次切换时调用目标视图的 `refresh()` 方法。

## 后端接口对应

GUI 调用与旧 API 端点对应关系：

| 旧 HTTP 端点 | GUI 调用 |
| --- | --- |
| `GET /projects` | `orchestrator.list_projects()` |
| `POST /projects` | `orchestrator.create_project(input)` |
| `PUT /projects/{id}` | `orchestrator.update_project(id, input)` |
| `DELETE /projects/{id}` | `project_service.delete(id)` + `task_service.delete_project(id)` |
| `GET /projects/{id}/snapshot` | `orchestrator.project_snapshot(id)` |
| `POST /projects/{id}/{step}` | `task_service.submit(...)` → `orchestrator.dispatch(...)` |
| `GET /tasks/{id}` | `task_service.get(id)` |
| `GET /projects/{id}/quality-report` | `build_quality_report(project)` |
| `DELETE /projects/{id}/artifacts/{key}` | `project_service.remove_artifact(id, key)` |

## 与旧前端的对应关系

| 旧前端模块 | 新 GUI 模块 |
| --- | --- |
| `step-meta.js` | `step_fields.py` |
| `scope-utils.js` | `scope_utils.py`（范围部分） |
| `planning-defaults.js` | `scope_utils.py`（默认值部分） |
| `structured-parsers.js` | `scope_utils.py`（解析部分） |
| `artifact-selectors.js` | `scope_utils.py`（产物选择部分） |
| `workspace-utils.js` | `widgets/form_builder.py` |
| `index-page.js` | `views/project_view.py` |
| `workflow-page.js` | `views/workflow_view.py` |
| `review-page.js` | `views/review_view.py` |
| `api-client.js` | 直接调用后端服务（无需 API 封装） |
