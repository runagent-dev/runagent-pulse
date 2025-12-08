"""Health endpoints."""
import time
from fastapi import APIRouter, Depends
from server.dependencies import get_db
from server.database import Database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: Database = Depends(get_db)):
    """Health check endpoint."""
    active_tasks = await db.count_active_tasks() if db else 0
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time()),
        "active_tasks": active_tasks,
    }

