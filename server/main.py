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
from typing import Optional, List
from pydantic import BaseModel
import hashlib
import json

from server.database import Database
from server.scheduler import Scheduler
from server.time_parser import TimeParser

# Configuration
API_KEY = os.getenv("PULSE_API_KEY", "")
DB_PATH = os.getenv("PULSE_DB_PATH", "/app/data/pulse.db")
TIMEZONE = os.getenv("PULSE_TIMEZONE", "UTC")

# Global instances
db: Optional[Database] = None
scheduler: Optional[Scheduler] = None
time_parser: Optional[TimeParser] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global db, scheduler, time_parser
    
    # Initialize
    db = Database(DB_PATH)
    await db.initialize()
    time_parser = TimeParser(timezone=TIMEZONE)
    scheduler = Scheduler(db, time_parser)
    await scheduler.restore_state()
    
    yield
    
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
    try:
        task_id = await scheduler.schedule_task(
            schedule_type=request.schedule_type,
            when=request.when,
            payload=request.payload,
            repeat=request.repeat,
            metadata=request.metadata
        )
        
        task = await db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")
        
        return ScheduleResponse(
            task_id=task_id,
            schedule_type=task["schedule_type"],
            next_execution=task["next_execution"],
            status=task["status"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

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
        success = await scheduler.claim_task(task_id, request.worker_id)
        if not success:
            raise HTTPException(status_code=409, detail="Task already claimed or not active")
        return {"status": "claimed"}
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
    try:
        next_execution = await scheduler.acknowledge_task(
            task_id=task_id,
            status=request.status,
            execution_time_ms=request.execution_time_ms,
            error=request.error,
            worker_id=request.worker_id
        )
        
        return AckResponse(next_execution=next_execution)
    except ValueError as e:
        # Check if it's a fencing token error (lock mismatch)
        if "Lock mismatch" in str(e):
             raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
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
    uvicorn.run(app, host=host, port=port)


