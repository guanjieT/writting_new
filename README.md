# Novel Agent Clean

这是一个重新梳理后的小说编写 agent 框架，目标是把“领域模型、Agent、服务、存储、API”拆开，让每层只做一件事。

默认实现使用 Mock LLM Provider，便于本地审查和跑通流程。只要切换环境变量，就可以替换成 OpenAI-compatible 的真实模型后端。
如果真实模型后端返回空响应或非 JSON 内容，后端现在会直接报出带上下文的错误信息，方便先排查上游接口、网关或模型输出格式。

项目启动时会自动读取根目录下的 [.env](.env)；建议先复制 [.env.example](.env.example) 作为本地配置模板。

代码语法最低需要 Python 3.10；当前机器如果没有 3.10+，可以先创建虚拟环境，但正式运行仍建议切到 3.10 或更高版本。

前端已经按多页面方式拆分完成，浏览器入口分别是 `/`、`/workflow`、`/outline`、`/volume-outline`、`/chapter-plan` 和 `/review`。项目中心负责创建、选择和编辑项目基础设定，编辑后会清空依赖产物、旧任务并回到起点；工作流页展示完整主链路并可按模块执行生成步骤，总纲页只管总纲和全书粗卷纲，卷纲页只管当前卷的完整卷纲和粗章纲，章节计划页只管当前章的完整章节计划，审查页负责查看产物与任务状态。页面之间会通过 `project_id` 和本地存储保持当前项目，不会在切页时丢失选择。工作流页与结构页里的参数字段都提供了字段级 `AI 补全` 按钮，可以在不重跑整步的前提下先补齐局部输入；补全请求会同时带上当前字段、同阶段表单约束和直接上游产物，例如角色框架里的 `role_capacity` 会进入 `core_roles` 和 `role_slots` 的补全上下文。现在每个 artifact 都会同时保存完整正文和结构化摘要，规划类产物已经改成固定结构输出，`content` 只保留摘要，结构化字段才是主体数据。总纲输出 `story_arcs`、`global_goals`、`main_conflicts`、`ending_direction`、`volume_plan_hints`；粗卷纲输出 `volumes`；卷纲输出 `volume_index`、`title`、`summary`、`goal`、`main_conflict`、`ending_hook`、`target_chapter_count`、`target_words`、`arc_segments`；粗章纲默认一次性生成整卷全部章节的 `chapters`，并用 `total_target_chapters` 做全卷校验；章节计划输出 `title`、`summary`、`chapter_type`、`pov_character`、`main_event`、`conflict`、`hook`、`target_words`、`min_words`、`characters`、`introduced_characters`、`scene_summaries`、`continuity_notes`、`writing_notes`。总纲拆成了 `总纲 -> 粗卷纲 -> 完整卷纲 -> 粗章纲 -> 完整章节计划` 的五段式锁式流水线，不再使用 `confirmed` 作为粗细切换开关。总纲、卷纲、章节计划和章节正文现在分别使用不同的上下文档位：总纲只读项目简报和上游核心摘要，卷纲读总纲摘要和当前卷约束，章节计划读卷纲摘要与相关设定摘要，章节正文读章节计划摘要和写作约束，避免把整份项目数据重复灌进 prompt。总纲页的 `chapters_per_volume` 现在会作为硬性目标传入生成流程，生成的每卷章节数不应再回落到默认 12。需求分析页会自动回填项目中心的 `premise -> requirements_text`、`target_audience -> audience`，并把项目约束合并到补充说明中；总纲页会自动回填 `outline_focus -> focus_points`，一致性页会把项目规则合并到 `known_rules`，让项目中心输入能更直接地进入步骤表单。

参数映射与传递审计文档见 [docs/parameter-flow-audit.md](docs/parameter-flow-audit.md)。

## 设计目标

- 业务逻辑和 HTTP 路由解耦。
- Prompt、LLM、存储都通过接口或适配器注入。
- Agent 只负责“组装上下文 + 调模型”，不直接碰文件系统。
- API 层只暴露明确的请求模型，不把内部对象泄露到路由里。
- 所有关键对象都能落盘、能回看、能审查。

## 启动方式

先安装依赖并确保 `.env` 已就位，然后启动服务：

```bash
python -m novel_agent.main
```

或直接：

```bash
uvicorn novel_agent.main:app --reload --host 127.0.0.1 --port 8001
```

默认监听 `127.0.0.1:8001`，如需修改可以设置 `NOVEL_AGENT_HOST` 和 `NOVEL_AGENT_PORT`。

启动后打开：

- `http://127.0.0.1:8001/`：项目中心
- `http://127.0.0.1:8001/workflow`：模块工作流
- `http://127.0.0.1:8001/outline`：总纲页面
- `http://127.0.0.1:8001/volume-outline`：卷纲页面
- `http://127.0.0.1:8001/chapter-plan`：章节计划页面
- `http://127.0.0.1:8001/review`：审查面板

## 环境变量

| 变量 | 含义 | 默认值 |
| --- | --- | --- |
| `NOVEL_AGENT_BASE_DIR` | 项目根目录 | 当前工作目录 |
| `NOVEL_AGENT_DATA_DIR` | 数据目录 | `./data` |
| `NOVEL_AGENT_PROMPTS_DIR` | prompt 目录 | `./prompts` |
| `NOVEL_AGENT_PROJECTS_DIR` | 项目 JSON 目录 | `./data/projects` |
| `NOVEL_AGENT_TASKS_DIR` | 任务 JSON 目录 | `./data/tasks` |
| `NOVEL_AGENT_AUDIT_LOG` | 审计日志 JSONL | `./data/audit/events.jsonl` |
| `NOVEL_AGENT_NAME` | 应用名称 | `Novel Agent Clean` |
| `NOVEL_AGENT_HOST` | 启动监听地址 | `127.0.0.1` |
| `NOVEL_AGENT_PORT` | 启动监听端口 | `8001` |
| `NOVEL_AGENT_CORS_ALLOW_ORIGINS` | CORS 白名单 | `*` |
| `NOVEL_AGENT_LLM_PROVIDER` | LLM 提供器 | `mock` |
| `NOVEL_AGENT_LLM_API_KEY` | 真实 LLM 密钥 | 自动读取 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` |
| `NOVEL_AGENT_LLM_BASE_URL` | 真实 LLM 基地址 | 自动读取 `OPENAI_BASE_URL` / `OPENAI_API_BASE` / `DEEPSEEK_BASE_URL` |
| `NOVEL_AGENT_LLM_MODEL` | 真实 LLM 模型名 | 自动读取 `OPENAI_MODEL` / `DEEPSEEK_MODEL` |
| `NOVEL_AGENT_LLM_TIMEOUT` | LLM 请求超时 | `60` |
| `NOVEL_AGENT_DEFAULT_TEMPERATURE` | 默认温度 | `0.7` |
| `NOVEL_AGENT_DEFAULT_MAX_TOKENS` | 默认输出长度 | `1200` |
| `NOVEL_AGENT_ENABLE_AUDIT` | 是否启用审计 | `true` |
| `NOVEL_AGENT_REQUIRE_PROMPT_FILES` | 启动时是否要求所有 prompt 文件存在 | `true` |

## 目录结构

```text
novel_agent_clean/
├── pyproject.toml
├── README.md
├── frontend/
│   ├── index.html
│   ├── workflow.html
│   ├── outline.html
│   ├── volume-outline.html
│   ├── chapter-plan.html
│   ├── review.html
│   └── assets/
│       ├── styles.css
│       └── js/
│           ├── api-client.js
│           ├── artifact-selectors.js
│           ├── dom.js
│           ├── index-page.js
│           ├── planning-defaults.js
│           ├── review-page.js
│           ├── scope-utils.js
│           ├── state.js
│           ├── step-meta.js
│           ├── structure-page.js
│           ├── structured-parsers.js
│           ├── workspace-utils.js
│           └── workflow-page.js
└── novel_agent/
    ├── __init__.py
    ├── api/
    │   ├── app.py
    │   ├── deps.py
    │   ├── schemas.py
    │   └── routes/
    │       ├── health.py
    │       ├── frontend.py
    │       ├── projects.py
    │       ├── workflow_steps.py
    │       ├── planning.py
    │       └── workflow.py
    ├── agents.py
    ├── config.py
    ├── container.py
    ├── domain.py
    ├── infrastructure.py
    ├── main.py
    ├── orchestrator.py
    ├── workflow_spec.py
    └── services.py
```

## 文件索引

| 文件 | 作用 | 公开内容 |
| --- | --- | --- |
| [novel_agent/config.py](novel_agent/config.py) | 读取环境变量并生成统一配置 | `AppConfig`，`load_config(base_dir=None)` |
| [novel_agent/domain.py](novel_agent/domain.py) | 核心领域模型、枚举、协议、异常 | `ProjectInput`、`ArtifactSummary`、`Artifact`、`NovelProject`、`AgentContext`、`AgentOutput`、`TaskRecord`、`AuditEvent`、`WorkflowStep`、`TaskStatus`、`ProjectNotFoundError`、`TaskNotFoundError`、`UnsupportedStepError`、`WorkflowOrderError` |
| [novel_agent/workflow_spec.py](novel_agent/workflow_spec.py) | 统一工作流顺序与依赖定义 | `WORKFLOW_STEPS`、`workflow_spec()`、`workflow_dependency_map()`、`workflow_label_map()` |
| [novel_agent/infrastructure.py](novel_agent/infrastructure.py) | 文件仓储、Prompt 存储、审计落盘、任务存储、LLM 适配器 | `FileProjectRepository`、`FilePromptStore`、`FileAuditSink`、`MemoryTaskStore`、`FileTaskStore`、`MockLLMProvider`、`OpenAICompatibleProvider` |
| [novel_agent/context_builder.py](novel_agent/context_builder.py) | 分阶段上下文装配与字段补全上下文压缩 | `build_generation_context()`、`build_completion_context()` |
| [novel_agent/services.py](novel_agent/services.py) | 业务服务层，负责编排存储、LLM 和任务 | `PromptService`、`LLMService`、`ProjectService`、`AuditService`、`TaskService`、`artifact_excerpt()`、`compact_artifact_context()`、`compact_artifacts_context()`、`build_artifact()`、`build_project_progress()`、`build_project_manuscript()`、`agent_context()` |
| [novel_agent/quality.py](novel_agent/quality.py) | 章节基础质量报告 | `build_quality_report()` |
| [novel_agent/agent_helpers.py](novel_agent/agent_helpers.py) | Agent 共用上下文辅助函数 | `build_outline_targets_json()`、`artifact_prompt_context()`、`chapter_plan_focus_from_context()` |
| [novel_agent/agents.py](novel_agent/agents.py) | Agent 定义，负责把项目上下文翻译成 prompt 并调用模型 | `AgentDependencies`、`BaseAgent`、`RequirementAgent`、`StoryBibleAgent`、`CharacterAgent`、`OutlineAgent`、`VolumeOutlineAgent`、`ChapterPlanAgent`、`ChapterAgent`、`RevisionAgent`、`ConsistencyAgent`、`MemoryAgent`、`build_agent_registry()` |
| [novel_agent/orchestrator.py](novel_agent/orchestrator.py) | 工作流编排器，负责 step 路由、项目状态更新、审计 | `NovelOrchestrator.build()`、`get_project()`、`list_projects()`、`dispatch()`、`create_project()`、`project_snapshot()` |
| [novel_agent/container.py](novel_agent/container.py) | 依赖注入容器，统一组装全部服务 | `AppContainer`、`build_container()`、`build_llm_provider()` |
| [novel_agent/api/schemas.py](novel_agent/api/schemas.py) | FastAPI 请求体和响应体模型 | `ProjectCreateRequest`、`FieldCompletionRequest`、`FieldCompletionResponse`、`RequirementsRequest`、`StoryBibleRequest`、`CharacterRequest`、`OutlineRequest`、`RoughVolumeOutlineRequest`、`VolumeOutlineRequest`、`RoughChapterPlanRequest`、`ChapterPlanRequest`、`ChapterRequest`、`RevisionRequest`、`ConsistencyRequest`、`MemoryRequest`、`ErrorResponse` |
| [novel_agent/api/deps.py](novel_agent/api/deps.py) | FastAPI 依赖注入入口 | `get_container(request)` |
| [novel_agent/api/app.py](novel_agent/api/app.py) | FastAPI 应用工厂、CORS、异常处理、路由装配 | `create_app(config=None)`、`app` |
| [novel_agent/api/routes/frontend.py](novel_agent/api/routes/frontend.py) | 前端页面路由 | `GET /`、`GET /workflow`、`GET /outline`、`GET /volume-outline`、`GET /chapter-plan`、`GET /review` |
| [novel_agent/api/routes/workflow.py](novel_agent/api/routes/workflow.py) | 工作流规范接口 | `GET /workflow/spec` |
| [novel_agent/api/routes/health.py](novel_agent/api/routes/health.py) | 健康检查路由 | `GET /health` |
| [novel_agent/api/routes/projects.py](novel_agent/api/routes/projects.py) | 项目 CRUD、基础设定更新、模块删除、快照、成稿导出和质量报告 | `POST /projects`、`PUT /projects/{project_id}`、`GET /projects`、`GET /projects/{project_id}`、`GET /projects/{project_id}/snapshot`、`GET /projects/{project_id}/exports/manuscript`、`GET /projects/{project_id}/quality-report`、`DELETE /projects/{project_id}/artifacts/{artifact_key}` |
| [novel_agent/api/routes/ai.py](novel_agent/api/routes/ai.py) | 字段级 AI 补全接口 | `POST /projects/{project_id}/field-completion` |
| [novel_agent/api/routes/planning.py](novel_agent/api/routes/planning.py) | 卷纲与章节计划入口 | `POST /projects/{project_id}/rough-volume-outline`、`POST /projects/{project_id}/volume-outline`、`POST /projects/{project_id}/rough-chapter-plan`、`POST /projects/{project_id}/chapter-plan` |
| [novel_agent/api/routes/workflow_steps.py](novel_agent/api/routes/workflow_steps.py) | 基础步骤入口和任务查询 | `POST /projects/{project_id}/requirements`、`story-bible`、`characters`、`outline`、`chapters`、`revision`、`consistency`、`memory`、`GET /projects/{project_id}/tasks`、`GET /tasks/{task_id}`、`POST /tasks/{task_id}/cancel` |
| [frontend/index.html](frontend/index.html) | 项目中心页面 | 创建项目、选择项目、进入工作流 |
| [frontend/workflow.html](frontend/workflow.html) | 主工作流页面 | 展示完整主链路、按步骤提交生成任务、自动轮询任务结果 |
| [frontend/outline.html](frontend/outline.html) | 总纲页面 | 聚焦总纲和全书粗卷纲 |
| [frontend/volume-outline.html](frontend/volume-outline.html) | 卷纲页面 | 聚焦当前卷的完整卷纲和粗章纲 |
| [frontend/chapter-plan.html](frontend/chapter-plan.html) | 章节计划页面 | 聚焦当前章的完整章节计划 |
| [frontend/review.html](frontend/review.html) | 审查面板页面 | 查看任务、产物、快照 |
| [frontend/assets/js/api-client.js](frontend/assets/js/api-client.js) | 前端 API 适配层 | `requestJson()`、`api.*`、`waitForTask()` |
| [frontend/assets/js/artifact-selectors.js](frontend/assets/js/artifact-selectors.js) | 前端产物与依赖选择 | `getArtifactForStep()`、`getStepReadiness()`、`isUnlocked()` |
| [frontend/assets/js/state.js](frontend/assets/js/state.js) | 前端状态与参数转换 | `getSelectedProjectId()`、`setSelectedProjectId()`、`listFromText()` |
| [frontend/assets/js/dom.js](frontend/assets/js/dom.js) | DOM 渲染辅助 | `escapeHtml()`、`renderNotice()`、`renderEmpty()` |
| [frontend/assets/js/index-page.js](frontend/assets/js/index-page.js) | 项目中心逻辑 | 创建与选择项目 |
| [frontend/assets/js/step-meta.js](frontend/assets/js/step-meta.js) | 前端步骤字段与分组元数据 | `STEP_META`、`PAGE_STEP_GROUPS`、`getStepMeta()` |
| [frontend/assets/js/workspace-utils.js](frontend/assets/js/workspace-utils.js) | 工作区通用表单与产物渲染 | `renderField()`、`renderDependencyList()`、`runStepFromForm()` |
| [frontend/assets/js/workflow-page.js](frontend/assets/js/workflow-page.js) | 主工作流逻辑 | 步骤解锁、任务提交、轮询刷新 |
| [frontend/assets/js/structure-page.js](frontend/assets/js/structure-page.js) | 结构页逻辑 | 总纲、卷纲、章节计划页面复用渲染 |
| [frontend/assets/js/review-page.js](frontend/assets/js/review-page.js) | 审查视图逻辑 | 快照、任务、产物展示 |
| [novel_agent/main.py](novel_agent/main.py) | 运行入口 | `app`、`create_app()` |

## 公开函数与参数

### `novel_agent/config.py`

- `load_config(base_dir: str | Path | None = None) -> AppConfig`
  - `base_dir`：可选项目根目录，不传则使用 `NOVEL_AGENT_BASE_DIR` 或当前工作目录。

### `novel_agent/infrastructure.py`

- `FileProjectRepository(projects_dir)`
  - `projects_dir`：项目 JSON 文件目录。
- `FilePromptStore(prompts_dir)`
  - `prompts_dir`：外部 prompt 模板目录。
- `FileAuditSink(audit_log_path)`
  - `audit_log_path`：JSONL 审计日志文件路径。
- `MemoryTaskStore()`
  - 无参数，测试和临时场景使用的纯内存任务仓储。
- `FileTaskStore(tasks_dir)`
  - `tasks_dir`：任务 JSON 文件目录，服务默认使用的持久化任务仓储。
- `MockLLMProvider.complete(prompt, system_prompt='', temperature=0.7, max_tokens=1200, metadata=None)`
  - `prompt`：用户提示词。
  - `system_prompt`：系统提示词。
  - `temperature`：生成随机性。
  - `max_tokens`：输出长度。
  - `metadata`：附加元数据，主要用于调试与审查。
- `OpenAICompatibleProvider(base_url, api_key, model, timeout=60.0)`
  - `base_url`：兼容 OpenAI 接口的服务地址。
  - `api_key`：访问密钥。
  - `model`：模型名。
  - `timeout`：请求超时秒数。

### `novel_agent/services.py`

- `PromptService.load(template_name)`
  - `template_name`：模板名，例如 `requirements`。
- `PromptService.render(template_name, variables)`
  - `variables`：用于模板格式化的变量字典。
- `LLMService.complete(prompt, system_prompt='', temperature=0.7, max_tokens=1200, metadata=None)`
  - 直接透传给 LLM provider。
- `ProjectService.create(project_input)`
  - `project_input`：`ProjectInput`。
- `ProjectService.get(project_id)`
  - `project_id`：项目编号。
- `ProjectService.list()`
  - 无参数。
- `ProjectService.save(project)`
  - `project`：完整项目对象。
- `ProjectService.remove_artifact(project_id, artifact_key)`
  - `artifact_key`：要删除的模块产物键，会连带清理依赖它的后续模块。
- `AuditService.record(action, project_id=None, actor='system', message='', payload=None)`
  - `action`：审计动作名。
  - `payload`：结构化附加信息。
- `TaskService.submit(project_id, task_name, job)`
  - `job`：无参数可调用对象，实际执行生成逻辑。
- `TaskService.get(task_id)`、`TaskService.list(project_id=None)`、`TaskService.cancel(task_id)`

### `novel_agent/agents.py`

- `BaseAgent.run(project, context, deps)`
  - `project`：当前项目。
  - `context`：温度、输出长度、请求体上下文。
  - `deps`：Prompt 与 LLM 服务依赖。
- 所有具体 Agent 都没有额外构造参数，默认由 `build_agent_registry()` 创建。

### `novel_agent/orchestrator.py`

- `NovelOrchestrator.build(project_service, audit_service, agent_dependencies)`
  - `project_service`：项目服务。
  - `audit_service`：审计服务。
  - `agent_dependencies`：Agent 依赖。
- `dispatch(project_id, step, payload)`
  - `step`：`requirements`、`story_bible`、`characters`、`outline`、`volume_outline`、`chapter_plan`、`chapter`、`revision`、`consistency`、`memory` 之一。
  - `payload`：接口请求体转成的字典。
- `create_project(project_input)`
  - `project_input`：项目创建输入。

## API 参数说明

### 创建项目

`POST /projects`

请求体字段：

- `title: string`
- `genre: string`
- `premise: string`
- `target_words: number`
- `target_volume_count: number`
- `target_chapters_per_volume: number`
- `target_audience: string`
- `tone: string[]`
- `style: string[]`
- `outline_focus: string[]`
- `core_requirements: string[]`
- `forbidden_elements: string[]`

### 需求分析

`POST /projects/{project_id}/requirements`

- `requirements_text: string`
- `audience: string`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 世界观生成

`POST /projects/{project_id}/story-bible`

- `theme: string`
- `world_rules: string[]`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 角色框架

`POST /projects/{project_id}/characters`

- `role_capacity: number`
- `core_roles: string[]`
- `role_slots: string[]`
- `role_rules: string[]`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 总纲生成

`POST /projects/{project_id}/outline`

- `volume_count: number`
- `chapters_per_volume: number`
- `focus_points: string[]`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 卷纲生成

`POST /projects/{project_id}/volume-outline`

- `volume_index: number`
- `volume_title: string`
- `volume_summary: string`
- `volume_goal: string`
- `volume_conflict: string`
- `volume_hook: string`
- `target_words: number`
- `target_chapter_count: number`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 粗卷纲

`POST /projects/{project_id}/rough-volume-outline`

- `volume_count: number`
- `chapters_per_volume: number`
- `notes: string[]`
- `temperature: number`
- 结果必须按卷分段输出，`content` 只保留摘要，`structured.volumes` 才是主体数据。
- `max_tokens: number`

### 章节计划

`POST /projects/{project_id}/chapter-plan`

- `volume_index: number`
- `chapter_index: number`
- `chapter_title: string`
- `chapter_summary: string`
- `chapter_type: string`
- `pov_character: string`
- `protagonist_present: boolean`
- `conflict: string`
- `hook: string`
- `target_words: number`
- `min_words: number`
- `characters: string[]`
- `introduced_characters: string[]`
- `scene_summaries: string[]`
- `plan_notes: string`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 粗章纲

`POST /projects/{project_id}/rough-chapter-plan`

- `volume_index: number`
- `total_target_chapters: number`
- `target_chapter_count: number`
- `notes: string[]`
- `temperature: number`
- 结果默认一次性生成整卷全部章节，`structured.chapters` 必须连续覆盖整卷。
- `max_tokens: number`

### 章节生成

`POST /projects/{project_id}/chapters`

- `volume_index: number`
- `chapter_index: number`
- `chapter_goal: string`
- `target_words: number`
- `scene_beats: string[]`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 修订

`POST /projects/{project_id}/revision`

- `volume_index: number`
- `chapter_index: number`
- `target_artifact: string`
- `instruction: string`
- `focus_areas: string[]`
- `temperature: number`
- `max_tokens: number`

### 一致性检查

`POST /projects/{project_id}/consistency`

- `volume_index: number`
- `chapter_index: number`
- `scope: string`
- `known_rules: string[]`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 记忆整理

`POST /projects/{project_id}/memory`

- `volume_index: number`
- `chapter_index: number`
- `query: string`
- `top_k: number`
- `notes: string[]`
- `temperature: number`
- `max_tokens: number`

### 任务查询

- `GET /projects/{project_id}/tasks`
- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/cancel`

## 审查重点

这个版本的关键审查点是：

- `domain.py` 只定义模型和协议，不做 I/O。
- `infrastructure.py` 只做存储与 LLM 适配，不写业务流程。
- `services.py` 只做业务操作封装，不直接暴露 HTTP。
- `agents.py` 只拼 prompt 和调用 LLM，不直接读文件或写数据库。
- `orchestrator.py` 是唯一的流程控制点。
- `api/` 只负责请求解析、调用编排器、返回响应。

如果你下一步要继续扩展，建议先补真实 LLM provider 和 prompt 文件，再做单元测试。

## `.env` 示例

推荐把真实密钥写进根目录的 `.env`，例如使用 DeepSeek：

```env
NOVEL_AGENT_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

如果用 OpenAI-compatible 服务，也可以写成：

```env
NOVEL_AGENT_LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```
