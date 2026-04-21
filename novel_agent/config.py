from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(raw_value: str | None, default: list[str]) -> list[str]:
    if not raw_value:
        return default
    items = [item.strip() for item in raw_value.split(",")]
    return [item for item in items if item]


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _first_env_float(*names: str, default: float) -> float:
    raw_value = _first_env(*names)
    if not raw_value:
        return default
    return float(raw_value)


def _first_env_int(*names: str, default: int) -> int:
    raw_value = _first_env(*names)
    if not raw_value:
        return default
    return int(raw_value)


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    data_dir: Path
    prompts_dir: Path
    projects_dir: Path
    tasks_dir: Path
    audit_log_path: Path
    app_name: str = "Novel Agent Clean"
    server_host: str = "127.0.0.1"
    server_port: int = 8001
    cors_allow_origins: list[str] = field(default_factory=lambda: ["*"])
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout: float = 60.0
    default_temperature: float = 0.7
    default_max_tokens: int = 1200
    enable_audit: bool = True
    audit_read_limit: int = 200


def load_config(base_dir: str | Path | None = None) -> AppConfig:
    resolved_base_dir = Path(base_dir or os.getenv("NOVEL_AGENT_BASE_DIR", Path.cwd())).resolve()
    data_dir = Path(os.getenv("NOVEL_AGENT_DATA_DIR", resolved_base_dir / "data")).resolve()
    prompts_dir = Path(os.getenv("NOVEL_AGENT_PROMPTS_DIR", resolved_base_dir / "prompts")).resolve()
    projects_dir = Path(_first_env("NOVEL_AGENT_PROJECTS_DIR", default=str(data_dir / "projects"))).resolve()
    tasks_dir = Path(_first_env("NOVEL_AGENT_TASKS_DIR", default=str(data_dir / "tasks"))).resolve()
    audit_log_path = Path(_first_env("NOVEL_AGENT_AUDIT_LOG", "NOVEL_AUDIT_LOG_PATH", default=str(data_dir / "audit" / "events.jsonl"))).resolve()

    data_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        base_dir=resolved_base_dir,
        data_dir=data_dir,
        prompts_dir=prompts_dir,
        projects_dir=projects_dir,
        tasks_dir=tasks_dir,
        audit_log_path=audit_log_path,
        app_name=os.getenv("NOVEL_AGENT_NAME", "Novel Agent Clean"),
        server_host=_first_env("NOVEL_AGENT_HOST", default="127.0.0.1"),
        server_port=_first_env_int("NOVEL_AGENT_PORT", default=8001),
        cors_allow_origins=_parse_csv(os.getenv("NOVEL_AGENT_CORS_ALLOW_ORIGINS"), ["*"]),
        llm_provider=_first_env("NOVEL_AGENT_LLM_PROVIDER", "NOVEL_LLM_PROVIDER", default="mock").lower() or "mock",
        llm_api_key=_first_env("NOVEL_AGENT_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"),
        llm_base_url=_first_env(
            "NOVEL_AGENT_LLM_BASE_URL",
            "NOVEL_LLM_BASE_URL",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "DEEPSEEK_BASE_URL",
            default="https://api.deepseek.com" if _first_env("NOVEL_AGENT_LLM_PROVIDER", "NOVEL_LLM_PROVIDER", default="mock").lower() == "deepseek" else "https://api.openai.com/v1",
        ),
        llm_model=_first_env(
            "NOVEL_AGENT_LLM_MODEL",
            "NOVEL_LLM_MODEL",
            "OPENAI_MODEL",
            "DEEPSEEK_MODEL",
            default="deepseek-chat" if _first_env("NOVEL_AGENT_LLM_PROVIDER", "NOVEL_LLM_PROVIDER", default="mock").lower() == "deepseek" else "gpt-4o-mini",
        ),
        llm_timeout=_first_env_float("NOVEL_AGENT_LLM_TIMEOUT", "NOVEL_LLM_TIMEOUT", default=60.0),
        default_temperature=_first_env_float("NOVEL_AGENT_DEFAULT_TEMPERATURE", default=0.7),
        default_max_tokens=_first_env_int("NOVEL_AGENT_DEFAULT_MAX_TOKENS", default=1200),
        enable_audit=_parse_bool(os.getenv("NOVEL_AGENT_ENABLE_AUDIT", os.getenv("NOVEL_AUDIT_ENABLED")), True),
        audit_read_limit=_first_env_int("NOVEL_AGENT_AUDIT_READ_LIMIT", "NOVEL_AUDIT_READ_LIMIT", default=200),
    )
