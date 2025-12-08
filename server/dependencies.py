"""FastAPI dependency helpers for shared resources."""
from fastapi import Request, HTTPException, Header
from typing import Optional
from server.database import Database
from server.scheduler import Scheduler
from server.services import TaskService
from runagent_pulse.tool_registry import ToolRegistry
from server.settings import Settings


def _get_from_state(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(status_code=500, detail=f"{name} not initialized")
    return value


def get_db(request: Request) -> Database:
    return _get_from_state(request, "db")


def get_scheduler(request: Request) -> Scheduler:
    return _get_from_state(request, "scheduler")


def get_task_service(request: Request) -> TaskService:
    return _get_from_state(request, "task_service")


def get_registry(request: Request) -> ToolRegistry:
    return _get_from_state(request, "registry")


def get_settings(request: Request) -> Settings:
    return _get_from_state(request, "settings")


async def verify_api_key(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> bool:
    settings = get_settings(request)
    if not settings.api_key:
        return True

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


