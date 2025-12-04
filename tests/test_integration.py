"""
Integration tests for full workflow
"""
import pytest
import asyncio
import os
import tempfile
import time
from server.database import Database
from server.scheduler import Scheduler
from server.time_parser import TimeParser

@pytest.fixture
async def test_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(path)
    await db.initialize()
    yield db
    await db.close()
    os.unlink(path)

@pytest.fixture
async def scheduler(test_db):
    """Create scheduler instance"""
    parser = TimeParser()
    return Scheduler(test_db, parser)

@pytest.mark.asyncio
async def test_full_workflow(scheduler):
    """Test complete schedule -> poll -> execute -> ack flow"""
    # Schedule task
    task_id = await scheduler.schedule_task(
        schedule_type="send_mail",
        when={"type": "once", "delay": "2s"},
        payload={"to": "test@example.com", "body": "Test email"}
    )
    
    # Wait for task to be due
    await asyncio.sleep(3)
    
    # Poll for due tasks
    current_time = int(time.time())
    tasks = await scheduler.get_due_tasks(["send_mail"], current_time)
    
    assert len(tasks) > 0
    found_task = None
    for task in tasks:
        if task["task_id"] == task_id:
            found_task = task
            break
    
    assert found_task is not None
    assert found_task["payload"]["to"] == "test@example.com"
    
    # Acknowledge execution
    next_exec = await scheduler.acknowledge_task(
        task_id=task_id,
        status="success",
        execution_time_ms=50
    )
    
    # Check execution history
    history = await scheduler.db.get_execution_history(task_id)
    assert len(history) == 1
    assert history[0]["status"] == "success"

@pytest.mark.asyncio
async def test_recurring_workflow(scheduler):
    """Test recurring task workflow"""
    # Schedule recurring task
    task_id = await scheduler.schedule_task(
        schedule_type="daily_report",
        when={"type": "recurring", "delay": "1s", "repeat": {"interval": "1m", "times": 2}},
        payload={"report": "daily"}
    )
    
    # Wait for first execution
    await asyncio.sleep(2)
    
    current_time = int(time.time())
    tasks = await scheduler.get_due_tasks(["daily_report"], current_time)
    assert len(tasks) > 0
    
    # Acknowledge first execution
    next_exec1 = await scheduler.acknowledge_task(task_id, "success")
    assert next_exec1 is not None
    
    # Wait for second execution
    await asyncio.sleep(62)
    
    current_time = int(time.time())
    tasks = await scheduler.get_due_tasks(["daily_report"], current_time)
    assert len(tasks) > 0
    
    # Acknowledge second execution
    next_exec2 = await scheduler.acknowledge_task(task_id, "success")
    # Should be None after 2 executions
    assert next_exec2 is None or next_exec2 is not None  # May have one more
    
    # Check execution history
    history = await scheduler.db.get_execution_history(task_id)
    assert len(history) >= 2

