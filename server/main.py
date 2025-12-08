"""
RunAgent Pulse Server
FastAPI-based scheduling service with SQLite persistence
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.settings import Settings, get_settings
from server.database import Database
from server.time_parser import TimeParser
from server.scheduler import Scheduler
from server.webhook_executor import WebhookExecutor
from server.services import TaskService
from server.mcp_tools import create_mcp_server
from server.workers import ExpirationWorker, WebhookWorker
from server.api import tasks, health, metrics, dashboard, tools, meta
from runagent_pulse.tool_registry import create_registry


def configure_logging(settings: Settings) -> None:
    log_level = settings.log_level
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    logging.getLogger("runagent_pulse").setLevel(log_level)
    logging.getLogger("runagent_pulse.scheduler").setLevel(log_level)
    logging.getLogger("runagent_pulse.time_parser").setLevel(log_level)


def build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings)
        logger = logging.getLogger("runagent_pulse")
        if settings.debug:
            logger.info("Debug mode enabled")

        db = Database(settings.db_path)
        await db.initialize()

        time_parser = TimeParser(timezone=settings.timezone)
        scheduler = Scheduler(db, time_parser)
        webhook_executor = WebhookExecutor(
            default_timeout=settings.webhook_default_timeout,
            default_retries=settings.webhook_default_retries,
        )

        await scheduler.restore_state()

        task_service = TaskService(db=db, scheduler=scheduler)
        registry = create_registry()

        app.state.settings = settings
        app.state.db = db
        app.state.scheduler = scheduler
        app.state.task_service = task_service
        app.state.registry = registry
        app.state.time_parser = time_parser

        expiration_worker = ExpirationWorker(
            scheduler=scheduler,
            interval_seconds=30,
            max_age_seconds=60,
        )
        webhook_worker = WebhookWorker(
            db=db,
            scheduler=scheduler,
            webhook_executor=webhook_executor,
            interval_seconds=settings.webhook_worker_interval,
            default_retries=settings.webhook_default_retries,
        )

        await expiration_worker.start()
        await webhook_worker.start()

        # Mount MCP server now that services are initialized
        mcp_server = create_mcp_server(
            db=db,
            scheduler=scheduler,
            task_service=task_service,
            registry=registry,
            settings=settings,
        )
        app.mount("/mcp", mcp_server)

        logger.info("Server startup complete")
        try:
            yield
        finally:
            await expiration_worker.stop()
            await webhook_worker.stop()
            await db.close()

    return lifespan


def add_cors(app: FastAPI, settings: Settings):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_allow_origins] if settings.cors_allow_origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def include_routers(app: FastAPI):
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(metrics.router)
    app.include_router(tools.router)
    app.include_router(meta.router)
    app.include_router(dashboard.router)


def mount_static(app: FastAPI):
    os.makedirs("server/static", exist_ok=True)
    app.mount("/dashboard", StaticFiles(directory="server/static", html=True), name="static")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RunAgent Pulse",
        description="Lightweight scheduling service for AI agents",
        version="0.1.0",
        lifespan=build_lifespan(settings),
    )

    add_cors(app, settings)
    include_routers(app)
    mount_static(app)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn_log_level = "debug" if settings.debug else "info"
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=uvicorn_log_level,
        access_log=True,
    )
