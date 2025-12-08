"""Task-related HTTP routes."""
import hashlib
import json
import logging
import time
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, AnyHttpUrl

from server.dependencies import (
    get_scheduler,
    get_task_service,
    get_db,
    verify_api_key,
    get_settings,
)
from server.scheduler import Scheduler
from server.services import TaskService
from server.database import Database
from server.settings import Settings

logger = logging.getLogger("runagent_pulse.tasks")
router = APIRouter(prefix="/tasks", tags=["tasks"])


class ScheduleRequest(BaseModel):
    schedule_type: str
    when: dict
    payload: dict
    repeat: Optional[dict] = None
    metadata: Optional[dict] = None
    webhook_url: Optional[AnyHttpUrl] = None
    webhook_timeout: Optional[int] = None
    webhook_retries: Optional[int] = None


class ScheduleResponse(BaseModel):
    task_id: str
    schedule_type: str
    next_execution: str
    status: str


class PollResponse(BaseModel):
    tasks: List[dict]
    next_poll_at: Optional[str] = None


class ClaimRequest(BaseModel):
    worker_id: str


class AckRequest(BaseModel):
    status: str
    execution_time_ms: Optional[int] = None
    error: Optional[str] = None
    worker_id: str
    execution_id: Optional[str] = None


class AckResponse(BaseModel):
    next_execution: Optional[str] = None


@router.post("/schedule", response_model=ScheduleResponse, dependencies=[Depends(verify_api_key)])
async def schedule_task(
    request: ScheduleRequest,
    task_service: TaskService = Depends(get_task_service),
    settings: Settings = Depends(get_settings),
):
    """Schedule a new task."""
    if settings.debug:
        logger.debug(
            "Schedule request received: schedule_type=%s, when=%s, repeat=%s, payload_keys=%s",
            request.schedule_type,
            request.when,
            request.repeat,
            list(request.payload.keys()) if request.payload else [],
        )

    if request.webhook_timeout is not None and request.webhook_timeout <= 0:
        raise HTTPException(status_code=400, detail="webhook_timeout must be > 0")
    if request.webhook_retries is not None and request.webhook_retries < 0:
        raise HTTPException(status_code=400, detail="webhook_retries must be >= 0")

    try:
        result = await task_service.schedule(request)
        if settings.debug:
            logger.debug("Task scheduled successfully: task_id=%s", result["task_id"])
        return ScheduleResponse(**result)
    except ValueError as exc:
        if settings.debug:
            logger.debug("Validation error: %s", exc, exc_info=True)
        else:
            logger.warning("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Internal error scheduling task: %s", exc, exc_info=settings.debug)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.get("/poll", response_model=PollResponse, dependencies=[Depends(verify_api_key)])
async def poll_tasks(
    types: str = Query(..., description="Comma-separated schedule types"),
    limit: int = Query(10, ge=1, le=100),
    etag: Optional[str] = Header(None),
    scheduler: Scheduler = Depends(get_scheduler),
):
    """Poll for due tasks (high-performance endpoint)."""
    try:
        schedule_types = [t.strip() for t in types.split(",")]
        current_time = int(time.time())

        tasks = await scheduler.get_due_tasks(
            schedule_types=schedule_types,
            current_time=current_time,
            limit=limit,
        )

        next_poll = await scheduler.get_next_task_time(schedule_types, current_time)

        tasks_json = json.dumps(tasks, sort_keys=True)
        tasks_etag = hashlib.md5(tasks_json.encode()).hexdigest()

        if etag and etag == tasks_etag:
            return JSONResponse(status_code=304)

        response = PollResponse(tasks=tasks, next_poll_at=next_poll)
        headers = {"ETag": tasks_etag, "X-Poll-Interval": "5"}

        return JSONResponse(content=response.dict(), headers=headers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.post("/{task_id}/claim", dependencies=[Depends(verify_api_key)])
async def claim_task(
    task_id: str,
    request: ClaimRequest,
    scheduler: Scheduler = Depends(get_scheduler),
):
    """Claim a task for execution."""
    try:
        execution_id = await scheduler.claim_task(task_id, request.worker_id)
        if not execution_id:
            raise HTTPException(status_code=409, detail="Task already claimed or not active")
        return {"status": "claimed", "execution_id": execution_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.post("/{task_id}/ack", response_model=AckResponse, dependencies=[Depends(verify_api_key)])
async def acknowledge_task(
    task_id: str,
    request: AckRequest,
    scheduler: Scheduler = Depends(get_scheduler),
    settings: Settings = Depends(get_settings),
):
    """Acknowledge task execution."""
    if settings.debug:
        logger.debug(
            "Acknowledge request: task_id=%s, status=%s, worker_id=%s, execution_time_ms=%s, error=%s",
            task_id,
            request.status,
            request.worker_id,
            request.execution_time_ms,
            request.error,
        )

    try:
        next_execution = await scheduler.acknowledge_task(
            task_id=task_id,
            status=request.status,
            execution_time_ms=request.execution_time_ms,
            error=request.error,
            worker_id=request.worker_id,
            execution_id=request.execution_id,
        )

        if settings.debug:
            logger.debug("Task %s acknowledged successfully. Next execution: %s", task_id, next_execution)

        return AckResponse(next_execution=next_execution)
    except ValueError as exc:
        if "Lock mismatch" in str(exc):
            if settings.debug:
                logger.debug("Lock mismatch for task %s: %s", task_id, exc)
            raise HTTPException(status_code=409, detail=str(exc))
        if settings.debug:
            logger.debug("ValueError for task %s: %s", task_id, exc, exc_info=True)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Internal error acknowledging task %s: %s", task_id, exc, exc_info=settings.debug)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.get("/{task_id}", dependencies=[Depends(verify_api_key)])
async def get_task(task_id: str, task_service: TaskService = Depends(get_task_service)):
    """Get task details."""
    task = await task_service.get_task(task_id)
    return task


@router.patch("/{task_id}", dependencies=[Depends(verify_api_key)])
async def update_task(
    task_id: str,
    updates: dict,
    scheduler: Scheduler = Depends(get_scheduler),
    db: Database = Depends(get_db),
):
    """Update task (pause, resume, modify)."""
    try:
        await scheduler.update_task(task_id, updates)
        task = await db.get_task(task_id)
        return task
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.delete("/{task_id}", dependencies=[Depends(verify_api_key)])
async def delete_task(
    task_id: str,
    scheduler: Scheduler = Depends(get_scheduler),
):
    """Cancel/delete task."""
    try:
        await scheduler.cancel_task(task_id)
        return {"status": "cancelled"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_tasks(
    status: Optional[str] = Query(None),
    schedule_type: Optional[str] = Query(None),
    start_time: Optional[int] = Query(None),
    end_time: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
):
    """List tasks with filters."""
    tasks = await db.list_tasks(
        status=status,
        schedule_type=schedule_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/{task_id}/history", dependencies=[Depends(verify_api_key)])
async def get_task_history(
    task_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Database = Depends(get_db),
):
    """Get execution history for a task."""
    history = await db.get_execution_history(task_id, limit=limit)
    return {"history": history}

