from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .agents import AgentDependencies
from .config import AppConfig, load_config
from .domain import LLMProvider
from .infrastructure import FileAuditSink, FileProjectRepository, FilePromptStore, MemoryTaskStore, MockLLMProvider, OpenAICompatibleProvider
from .orchestrator import NovelOrchestrator
from .services import AuditService, LLMService, ProjectService, PromptService, TaskService


def build_llm_provider(config: AppConfig) -> LLMProvider:
    if config.llm_provider in {"openai-compatible", "openai", "deepseek"} and config.llm_api_key and config.llm_base_url and config.llm_model:
        return OpenAICompatibleProvider(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
            timeout=config.llm_timeout,
        )
    return MockLLMProvider()


@dataclass
class AppContainer:
    config: AppConfig
    project_service: ProjectService
    prompt_service: PromptService
    llm_service: LLMService
    audit_service: AuditService
    task_service: TaskService
    orchestrator: NovelOrchestrator


def build_container(config: AppConfig | None = None) -> AppContainer:
    resolved_config = config or load_config()
    project_repository = FileProjectRepository(resolved_config.projects_dir)
    prompt_store = FilePromptStore(resolved_config.prompts_dir)
    audit_sink = FileAuditSink(resolved_config.audit_log_path)
    task_store = MemoryTaskStore()
    provider = build_llm_provider(resolved_config)

    prompt_service = PromptService(prompt_store)
    llm_service = LLMService(provider)
    project_service = ProjectService(project_repository)
    audit_service = AuditService(audit_sink if resolved_config.enable_audit else None)
    task_service = TaskService(task_store, ThreadPoolExecutor(max_workers=4))
    orchestrator = NovelOrchestrator.build(
        project_service=project_service,
        audit_service=audit_service,
        agent_dependencies=AgentDependencies(prompt_service=prompt_service, llm_service=llm_service),
        task_service=task_service,
    )

    return AppContainer(
        config=resolved_config,
        project_service=project_service,
        prompt_service=prompt_service,
        llm_service=llm_service,
        audit_service=audit_service,
        task_service=task_service,
        orchestrator=orchestrator,
    )
