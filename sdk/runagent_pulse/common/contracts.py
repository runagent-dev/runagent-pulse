"""Shared contracts (request/response models) for tools/endpoints."""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel

# Reuse existing SDK models where possible
from runagent_pulse.models import (
    ScheduleTaskParams,
    ListTasksParams,
    CancelTaskParams,
    GetTaskDetailsParams,
)


class ScheduleTaskResponse(BaseModel):
    task_id: str
    schedule_type: str
    next_execution: Optional[str] = None
    status: Optional[str] = None


class ListTasksResponse(BaseModel):
    tasks: List[Dict[str, Any]]
    count: int


class CancelTaskResponse(BaseModel):
    success: bool
    task_id: str
    message: str


class GetTaskDetailsResponse(BaseModel):
    task: Optional[Dict[str, Any]] = None
    execution_history: List[Dict[str, Any]] = []
    history_count: int = 0


