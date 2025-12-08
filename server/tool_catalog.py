"""Central catalog of tools with exposure flags."""
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any, List, Optional, Sequence

from runagent_pulse.common import contracts
from runagent_pulse.common.tooling import TOOL_META
from server.services import TaskService
from server.database import Database
from server.scheduler import Scheduler
from server.settings import Settings


@dataclass
class ToolContext:
    task_service: TaskService
    db: Database
    scheduler: Scheduler
    settings: Settings


ToolHandler = Callable[[ToolContext, Any], Awaitable[Any]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    request_model: Any
    response_model: Optional[Any]
    impl: ToolHandler
    expose_http: bool = True
    expose_mcp: bool = True
    expose_frameworks: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)


# Implementations using TaskService and existing services
async def schedule_task_impl(ctx: ToolContext, params: contracts.ScheduleTaskParams):
    return await ctx.task_service.schedule(params)


async def list_tasks_impl(ctx: ToolContext, params: contracts.ListTasksParams):
    return await ctx.task_service.list_tasks(params)


async def cancel_task_impl(ctx: ToolContext, params: contracts.CancelTaskParams):
    return await ctx.task_service.cancel_task(params)


async def get_task_details_impl(ctx: ToolContext, params: contracts.GetTaskDetailsParams):
    return await ctx.task_service.get_task_details(params)


_IMPL_BY_NAME = {
    "schedule_task": schedule_task_impl,
    "list_tasks": list_tasks_impl,
    "cancel_task": cancel_task_impl,
    "get_task_details": get_task_details_impl,
}


def _build_tools() -> List[ToolDefinition]:
    tools: List[ToolDefinition] = []
    for meta in TOOL_META:
        impl = _IMPL_BY_NAME.get(meta.name)
        if not impl:
            continue
        tools.append(
            ToolDefinition(
                name=meta.name,
                description=meta.description,
                request_model=meta.request_model,
                response_model=meta.response_model,
                impl=impl,
                expose_http=meta.expose_http,
                expose_mcp=meta.expose_mcp,
                expose_frameworks=meta.expose_frameworks,
                tags=meta.tags,
            )
        )
    return tools


TOOLS: List[ToolDefinition] = _build_tools()


def list_tools() -> List[ToolDefinition]:
    return TOOLS


def list_tools_for(
    exposure: str,
    framework: Optional[str] = None,
) -> List[ToolDefinition]:
    if exposure == "http":
        return [t for t in TOOLS if t.expose_http]
    if exposure == "mcp":
        return [t for t in TOOLS if t.expose_mcp]
    if exposure == "framework" and framework:
        return [t for t in TOOLS if framework in t.expose_frameworks]
    return []

