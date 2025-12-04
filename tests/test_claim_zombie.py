import pytest
import asyncio
import os
import time
from server.database import Database
from server.scheduler import Scheduler
from server.time_parser import TimeParser

@pytest.mark.asyncio
async def test_claim_task_concurrency():
    # Setup
    db_path = "/tmp/test_pulse_claim_v2.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = Database(db_path)
    await db.initialize()
    
    time_parser = TimeParser()
    scheduler = Scheduler(db, time_parser)
    
    # Create a task
    task_id = await scheduler.schedule_task(
        schedule_type="test_claim",
        when={"type": "once", "natural": "in 1 minute"},
        payload={"data": "test"}
    )
    
    # Worker 1 claims
    success1 = await scheduler.claim_task(task_id, "worker1")
    assert success1 is True
    
    # Worker 2 tries to claim (should fail)
    success2 = await scheduler.claim_task(task_id, "worker2")
    assert success2 is False
    
    # Verify status
    task = await db.get_task(task_id)
    assert task["status"] == "processing"
    assert task["metadata"]["locked_by"] == "worker1"
    
    # Simulate zombie task (manually expire lease by updating locked_at)
    # We set locked_at to 1 hour ago
    expired_time = int(time.time()) - 3600
    task["metadata"]["locked_at"] = expired_time
    await db.update_task(task_id, {"metadata": task["metadata"]})
    
    # Worker 2 tries to claim again (should succeed now as lease expired)
    # Note: claim_task default timeout is 300s
    success3 = await db.claim_task(task_id, "worker2", lease_timeout=300)
    assert success3 is True
    
    # Verify new owner
    task = await db.get_task(task_id)
    assert task["metadata"]["locked_by"] == "worker2"
    
    await db.close()
    os.remove(db_path)
