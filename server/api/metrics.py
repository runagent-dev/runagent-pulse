"""Metrics endpoint."""
from fastapi import APIRouter, Depends
from server.dependencies import get_db
from server.database import Database

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics(db: Database = Depends(get_db)):
    """Prometheus metrics endpoint."""
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

