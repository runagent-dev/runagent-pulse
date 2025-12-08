"""
Service layer for task operations shared by FastAPI endpoints and MCP tools.
"""
from typing import Dict, Any
from fastapi import HTTPException
from dateutil import parser as date_parser
from runagent_pulse.models import (
    ScheduleTaskParams,
    ListTasksParams,
    CancelTaskParams,
    GetTaskDetailsParams,
)


class TaskService:
    """Shared task service used by HTTP endpoints and MCP tools."""

    def __init__(self, db, scheduler):
        self.db = db
        self.scheduler = scheduler

    async def schedule(self, params) -> Dict[str, Any]:
        # Normalize string inputs (tools send "when" as str) to the scheduler's dict format
        when = params.when
        if isinstance(when, str):
            try:
                # ISO-ish datetime strings
                date_parser.parse(when)
                when = {"type": "once", "time": when}
            except Exception:
                # Natural language fall-back
                when = {"type": "once", "natural": when}
        elif not isinstance(when, dict):
            raise ValueError(f"Invalid 'when' format: {when}")

        task_id = await self.scheduler.schedule_task(
            schedule_type=params.schedule_type,
            when=when,
            payload=params.payload,
            repeat=params.repeat,
            metadata=params.metadata,
            webhook_url=params.webhook_url,
            webhook_timeout=params.webhook_timeout,
            webhook_retries=params.webhook_retries,
        )
        task = await self.db.get_task(task_id)
        return {
            "task_id": task_id,
            "schedule_type": params.schedule_type,
            "next_execution": task.get("next_execution_iso") if task else None,
            "status": task.get("status") if task else None,
        }

    async def list_tasks(self, params: ListTasksParams) -> Dict[str, Any]:
        tasks = await self.db.list_tasks(**params.model_dump(exclude_unset=True))
        return {"tasks": tasks, "count": len(tasks)}

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        task = await self.db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    async def get_task_details(self, params: GetTaskDetailsParams) -> Dict[str, Any]:
        task = await self.db.get_task(params.task_id)
        if not task:
            return {"error": f"Task {params.task_id} not found"}
        history = await self.db.get_execution_history(params.task_id, limit=5)
        return {
            "task": task,
            "execution_history": history,
            "history_count": len(history),
        }

    async def cancel_task(self, params: CancelTaskParams) -> Dict[str, Any]:
        await self.scheduler.cancel_task(params.task_id)
        return {"success": True, "task_id": params.task_id, "message": "Task cancelled successfully"}


