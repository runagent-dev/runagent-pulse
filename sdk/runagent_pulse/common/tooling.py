"""Shared tool metadata (no implementations)."""
from dataclasses import dataclass, field
from typing import Optional, Sequence, Any, List

from runagent_pulse.common import contracts


@dataclass
class ToolMeta:
    name: str
    description: str
    request_model: Any
    response_model: Optional[Any]
    expose_http: bool = True
    expose_mcp: bool = True
    expose_frameworks: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)


TOOL_META: List[ToolMeta] = [
    ToolMeta(
        name="schedule_task",
        description="Schedule a task for future execution",
        request_model=contracts.ScheduleTaskParams,
        response_model=contracts.ScheduleTaskResponse,
        expose_frameworks=("langgraph", "crewai"),
        tags=("tasks",),
    ),
    ToolMeta(
        name="list_tasks",
        description="List tasks with optional filters",
        request_model=contracts.ListTasksParams,
        response_model=contracts.ListTasksResponse,
        expose_frameworks=("langgraph", "crewai"),
        tags=("tasks",),
    ),
    ToolMeta(
        name="cancel_task",
        description="Cancel a scheduled task",
        request_model=contracts.CancelTaskParams,
        response_model=contracts.CancelTaskResponse,
        expose_frameworks=("langgraph", "crewai"),
        tags=("tasks",),
    ),
    ToolMeta(
        name="get_task_details",
        description="Get details and history for a task",
        request_model=contracts.GetTaskDetailsParams,
        response_model=contracts.GetTaskDetailsResponse,
        expose_frameworks=("langgraph", "crewai"),
        tags=("tasks",),
    ),
]


