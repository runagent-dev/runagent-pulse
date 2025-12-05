"""
RunAgent Pulse Server
FastAPI-based scheduling service with SQLite persistence
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import time
import logging
from typing import Optional, List
from pydantic import BaseModel, AnyHttpUrl
import hashlib
import json

from server.database import Database
from server.scheduler import Scheduler
from server.time_parser import TimeParser
from server.webhook_executor import WebhookExecutor

# Configuration
API_KEY = os.getenv("PULSE_API_KEY", "")
DB_PATH = os.getenv("PULSE_DB_PATH", "/app/data/pulse.db")
TIMEZONE = os.getenv("PULSE_TIMEZONE", "UTC")
DEBUG = os.getenv("PULSE_DEBUG", "false").lower() == "true"
WEBHOOK_DEFAULT_TIMEOUT = int(os.getenv("PULSE_WEBHOOK_TIMEOUT", "30"))
WEBHOOK_DEFAULT_RETRIES = int(os.getenv("PULSE_WEBHOOK_RETRIES", "3"))
WEBHOOK_WORKER_INTERVAL = int(os.getenv("PULSE_WEBHOOK_INTERVAL", "10"))

# Configure logging - DEBUG mode uses DEBUG level, otherwise INFO
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing configuration
)
logger = logging.getLogger("runagent_pulse")
logger.setLevel(log_level)

# Set level for child loggers
logging.getLogger("runagent_pulse.scheduler").setLevel(log_level)
logging.getLogger("runagent_pulse.time_parser").setLevel(log_level)

if DEBUG:
    logger.info("Debug mode enabled")

# Global instances
db: Optional[Database] = None
scheduler: Optional[Scheduler] = None
time_parser: Optional[TimeParser] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global db, scheduler, time_parser
    
    import asyncio
    
    logger.info(f"Starting RunAgent Pulse server (DEBUG={DEBUG})")
    if DEBUG:
        logger.debug("DEBUG MODE: Detailed logging enabled")
    
    # Initialize
    db = Database(DB_PATH)
    await db.initialize()
    time_parser = TimeParser(timezone=TIMEZONE)
    scheduler = Scheduler(db, time_parser)
    webhook_executor = WebhookExecutor(
        default_timeout=WEBHOOK_DEFAULT_TIMEOUT,
        default_retries=WEBHOOK_DEFAULT_RETRIES,
    )
    await scheduler.restore_state()
    
    # Start background expiration checker
    async def expiration_checker():
        while True:
            try:
                await scheduler.expire_unclaimed_tasks(max_age_seconds=60)
            except Exception as e:
                logger.error(f"Error in expiration checker: {e}", exc_info=DEBUG)
            await asyncio.sleep(30)  # Check every 30 seconds
    
    expiration_task = asyncio.create_task(expiration_checker())

    async def webhook_worker():
        worker_id = "webhook-worker"
        while True:
            try:
                current_time = int(time.time())
                tasks = await db.get_due_webhook_tasks(current_time, limit=100)

                for task in tasks:
                    task_id = task["task_id"]
                    metadata = task.get("metadata") or {}
                    max_retries = metadata.get("webhook_retries", WEBHOOK_DEFAULT_RETRIES)
                    attempts = metadata.get("webhook_attempts", 0)

                    # Guard against stuck tasks that already exhausted retries
                    if attempts >= max_retries:
                        metadata["webhook_final_failure"] = True
                        await db.update_task(task_id, {"metadata": metadata})
                        await scheduler.acknowledge_task(
                            task_id=task_id,
                            status="failed",
                            error="max retries exceeded",
                            worker_id=worker_id,
                            execution_id=None,
                        )
                        continue

                    execution_id = await scheduler.claim_task(task_id, worker_id)
                    if not execution_id:
                        continue

                    if DEBUG:
                        logger.debug(f"Executing webhook for task {task_id} (attempt {attempts + 1}/{max_retries})")
                    success, error_message = await webhook_executor.execute_webhook(task, execution_id)

                    if success:
                        if DEBUG:
                            logger.debug(f"Webhook successful for task {task_id}")
                        # Reset attempts on success
                        if attempts:
                            metadata["webhook_attempts"] = 0
                            await db.update_task(task_id, {"metadata": metadata})
                        await scheduler.acknowledge_task(
                            task_id=task_id,
                            status="success",
                            worker_id=worker_id,
                            execution_id=execution_id,
                        )
                        continue

                    # Failure: increment attempts and decide on retry/final failure
                    attempts += 1
                    metadata["webhook_attempts"] = attempts
                    if DEBUG:
                        logger.debug(f"Webhook failed for task {task_id}: {error_message} (attempt {attempts}/{max_retries})")

                    await db.record_execution(
                        task_id=task_id,
                        execution_id=execution_id,
                        executed_at=int(time.time()),
                        status="failed",
                        error=error_message,
                    )

                    if attempts >= max_retries:
                        metadata["webhook_final_failure"] = True
                        await db.update_task(task_id, {"metadata": metadata})
                        await scheduler.acknowledge_task(
                            task_id=task_id,
                            status="failed",
                            error=error_message,
                            worker_id=worker_id,
                            execution_id=execution_id,
                        )
                        continue

                    # Retry with exponential backoff (1s, 2s, 4s, capped at 60s)
                    backoff_seconds = min(2 ** (attempts - 1), 60)
                    next_run = int(time.time()) + backoff_seconds

                    # Update task for retry
                    await db.update_task(task_id, {
                        "status": "active",
                        "next_execution": next_run,
                        "metadata": metadata
                    })
                    await db.add_to_time_bucket(next_run, task_id)

            except Exception as e:
                logger.error(f"Error in webhook worker: {e}", exc_info=DEBUG)

            await asyncio.sleep(WEBHOOK_WORKER_INTERVAL)

    webhook_worker_task = asyncio.create_task(webhook_worker())
    
    logger.info("Server startup complete")
    if DEBUG:
        logger.debug("DEBUG MODE: All components initialized")
    
    try:
        yield
    finally:
        expiration_task.cancel()
        try:
            await expiration_task
        except asyncio.CancelledError:
            pass
        webhook_worker_task.cancel()
        try:
            await webhook_worker_task
        except asyncio.CancelledError:
            pass
    
    # Cleanup
    if db:
        await db.close()

app = FastAPI(
    title="RunAgent Pulse",
    description="Lightweight scheduling service for AI agents",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
async def verify_api_key(authorization: Optional[str] = Header(None)):
    """Optional API key authentication"""
    if not API_KEY:
        return True  # No auth required
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True

# Request/Response Models
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

class AckRequest(BaseModel):
    status: str
    execution_time_ms: Optional[int] = None
    error: Optional[str] = None
    worker_id: str
    execution_id: Optional[str] = None

class AckResponse(BaseModel):
    next_execution: Optional[str] = None

# API Endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    active_tasks = await db.count_active_tasks() if db else 0
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time()),
        "active_tasks": active_tasks
    }

@app.post("/tasks/schedule", response_model=ScheduleResponse)
async def schedule_task(
    request: ScheduleRequest,
    _: bool = Depends(verify_api_key)
):
    """Schedule a new task"""
    if DEBUG:
        logger.debug(f"Schedule request received: schedule_type={request.schedule_type}, when={request.when}, repeat={request.repeat}, payload_keys={list(request.payload.keys()) if request.payload else []}")

    # Basic validation for webhook parameters
    if request.webhook_timeout is not None and request.webhook_timeout <= 0:
        raise HTTPException(status_code=400, detail="webhook_timeout must be > 0")
    if request.webhook_retries is not None and request.webhook_retries < 0:
        raise HTTPException(status_code=400, detail="webhook_retries must be >= 0")
    
    try:
        task_id = await scheduler.schedule_task(
            schedule_type=request.schedule_type,
            when=request.when,
            payload=request.payload,
            repeat=request.repeat,
            metadata=request.metadata,
            webhook_url=request.webhook_url,
            webhook_timeout=request.webhook_timeout or WEBHOOK_DEFAULT_TIMEOUT,
            webhook_retries=request.webhook_retries or WEBHOOK_DEFAULT_RETRIES,
        )
        
        if DEBUG:
            logger.debug(f"Task scheduled successfully: task_id={task_id}")
        
        task = await db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")
        
        # Use next_execution_iso from database, or convert if not available
        next_execution_iso = task.get("next_execution_iso")
        if not next_execution_iso and task.get("next_execution"):
            from datetime import datetime
            next_execution_iso = datetime.utcfromtimestamp(task["next_execution"]).isoformat() + "Z"
        
        return ScheduleResponse(
            task_id=task_id,
            schedule_type=task["schedule_type"],
            next_execution=next_execution_iso or "",
            status=task["status"]
        )
    except ValueError as e:
        error_msg = str(e)
        if DEBUG:
            logger.debug(f"Validation error: {error_msg}", exc_info=True)
        else:
            logger.warning(f"Validation error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Internal error: {str(e)}"
        logger.error(error_msg, exc_info=DEBUG)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/tasks/poll", response_model=PollResponse)
async def poll_tasks(
    types: str = Query(..., description="Comma-separated schedule types"),
    limit: int = Query(10, ge=1, le=100),
    etag: Optional[str] = Header(None),
    _: bool = Depends(verify_api_key)
):
    """Poll for due tasks (high-performance endpoint)"""
    try:
        schedule_types = [t.strip() for t in types.split(",")]
        current_time = int(time.time())
        
        tasks = await scheduler.get_due_tasks(
            schedule_types=schedule_types,
            current_time=current_time,
            limit=limit
        )
        
        # Calculate next poll time
        next_poll = await scheduler.get_next_task_time(schedule_types, current_time)
        
        # Generate ETag
        tasks_json = json.dumps(tasks, sort_keys=True)
        tasks_etag = hashlib.md5(tasks_json.encode()).hexdigest()
        
        # Check ETag
        if etag and etag == tasks_etag:
            return JSONResponse(status_code=304)
        
        response = PollResponse(
            tasks=tasks,
            next_poll_at=next_poll
        )
        
        headers = {
            "ETag": tasks_etag,
            "X-Poll-Interval": "5"  # Suggest 5 second polling
        }
        
        return JSONResponse(
            content=response.dict(),
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

class ClaimRequest(BaseModel):
    worker_id: str

@app.post("/tasks/{task_id}/claim")
async def claim_task(
    task_id: str,
    request: ClaimRequest,
    _: bool = Depends(verify_api_key)
):
    """Claim a task for execution"""
    try:
        execution_id = await scheduler.claim_task(task_id, request.worker_id)
        if not execution_id:
            raise HTTPException(status_code=409, detail="Task already claimed or not active")
        return {"status": "claimed", "execution_id": execution_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.post("/tasks/{task_id}/ack", response_model=AckResponse)
async def acknowledge_task(
    task_id: str,
    request: AckRequest,
    _: bool = Depends(verify_api_key)
):
    """Acknowledge task execution"""
    if DEBUG:
        logger.debug(f"Acknowledge request: task_id={task_id}, status={request.status}, worker_id={request.worker_id}, execution_time_ms={request.execution_time_ms}, error={request.error}")
    
    try:
        next_execution = await scheduler.acknowledge_task(
            task_id=task_id,
            status=request.status,
            execution_time_ms=request.execution_time_ms,
            error=request.error,
            worker_id=request.worker_id,
            execution_id=request.execution_id
        )
        
        if DEBUG:
            logger.debug(f"Task {task_id} acknowledged successfully. Next execution: {next_execution}")
        
        return AckResponse(next_execution=next_execution)
    except ValueError as e:
        # Check if it's a fencing token error (lock mismatch)
        if "Lock mismatch" in str(e):
            if DEBUG:
                logger.debug(f"Lock mismatch for task {task_id}: {str(e)}")
            raise HTTPException(status_code=409, detail=str(e))
        if DEBUG:
            logger.debug(f"ValueError for task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Internal error acknowledging task {task_id}: {str(e)}", exc_info=DEBUG)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    _: bool = Depends(verify_api_key)
):
    """Get task details"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    updates: dict,
    _: bool = Depends(verify_api_key)
):
    """Update task (pause, resume, modify)"""
    try:
        await scheduler.update_task(task_id, updates)
        task = await db.get_task(task_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    _: bool = Depends(verify_api_key)
):
    """Cancel/delete task"""
    try:
        await scheduler.cancel_task(task_id)
        return {"status": "cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

from fastapi.staticfiles import StaticFiles

# ... (existing imports)

# ... (app definition)

# Mount static files for Dashboard UI
# Ensure directory exists
os.makedirs("server/static", exist_ok=True)
app.mount("/dashboard", StaticFiles(directory="server/static", html=True), name="static")

@app.get("/")
async def root():
    """Redirect to dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

# ... (existing endpoints)

@app.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    schedule_type: Optional[str] = Query(None),
    start_time: Optional[int] = Query(None),
    end_time: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: bool = Depends(verify_api_key)
):
    """List tasks with filters"""
    tasks = await db.list_tasks(
        status=status,
        schedule_type=schedule_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    return {"tasks": tasks, "count": len(tasks)}

@app.get("/tasks/{task_id}/history")
async def get_task_history(
    task_id: str,
    limit: int = Query(100, ge=1, le=1000),
    _: bool = Depends(verify_api_key)
):
    """Get execution history for a task"""
    history = await db.get_execution_history(task_id, limit=limit)
    return {"history": history}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    active_tasks = await db.count_active_tasks() if db else 0
    total_executions = await db.count_total_executions() if db else 0
    
    metrics_text = f"""# HELP pulse_tasks_active Number of active tasks
# TYPE pulse_tasks_active gauge
pulse_tasks_active {active_tasks}

# HELP pulse_tasks_executed_total Total tasks executed
# TYPE pulse_tasks_executed_total counter
pulse_tasks_executed_total {total_executions}
"""
    return metrics_text

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("PULSE_HOST", "0.0.0.0")
    port = int(os.getenv("PULSE_PORT", "8000"))
    # Set uvicorn log level based on DEBUG flag
    uvicorn_log_level = "debug" if DEBUG else "info"
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level=uvicorn_log_level,
        access_log=True
    )



