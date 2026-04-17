from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from ..config import AppConfig, load_config
from ..container import build_container
from ..domain import ProjectNotFoundError, TaskNotFoundError, UnsupportedStepError, WorkflowOrderError
from .routes.ai import router as ai_router
from .routes.frontend import router as frontend_router
from .routes.health import router as health_router
from .routes.planning import router as planning_router
from .routes.projects import router as projects_router
from .routes.workflow import router as workflow_router
from .routes.workflow_steps import router as workflow_steps_router


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def _install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found_handler(_: Request, exc: ProjectNotFoundError):
        return JSONResponse(status_code=404, content={"detail": f"project not found: {exc}"})

    @app.exception_handler(UnsupportedStepError)
    async def unsupported_step_handler(_: Request, exc: UnsupportedStepError):
        return JSONResponse(status_code=400, content={"detail": f"unsupported step: {exc}"})

    @app.exception_handler(WorkflowOrderError)
    async def workflow_order_handler(_: Request, exc: WorkflowOrderError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(_: Request, exc: TaskNotFoundError):
        return JSONResponse(status_code=404, content={"detail": f"task not found: {exc}"})

    @app.exception_handler(LookupError)
    async def lookup_error_handler(_: Request, exc: LookupError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})


def _install_cors(app: FastAPI, config: AppConfig) -> None:
    allow_all = "*" in config.cors_allow_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else config.cors_allow_origins,
        allow_credentials=not allow_all,
        allow_methods=["*"] if not allow_all else ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"] if not allow_all else ["Accept", "Content-Type", "Authorization"],
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    resolved_config = config or load_config()
    container = build_container(resolved_config)

    app = FastAPI(title=resolved_config.app_name)
    app.state.container = container
    _install_cors(app, resolved_config)
    _install_exception_handlers(app)

    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(ai_router)
    app.include_router(planning_router)
    app.include_router(workflow_steps_router)
    app.include_router(workflow_router)
    app.include_router(frontend_router)
    return app


app = create_app()
