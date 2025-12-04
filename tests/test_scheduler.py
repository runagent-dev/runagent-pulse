"""
Tests for scheduler
"""
import pytest
import asyncio
import os
import tempfile
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
async def test_schedule_task(scheduler):
    """Test task scheduling"""
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "once", "delay": "1m"},
        payload={"test": "data"}
    )
    assert task_id is not None
    
    task = await scheduler.db.get_task(task_id)
    assert task is not None
    assert task["schedule_type"] == "test_task"

@pytest.mark.asyncio
async def test_get_due_tasks(scheduler):
    """Test getting due tasks"""
    # Schedule a task for immediate execution
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "once", "delay": "0s"},
        payload={"test": "data"}
    )
    
    import time
    await asyncio.sleep(1)  # Wait a bit
    
    current_time = int(time.time())
    tasks = await scheduler.get_due_tasks(["test_task"], current_time)
    assert len(tasks) > 0

@pytest.mark.asyncio
async def test_acknowledge_task(scheduler):
    """Test task acknowledgment"""
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "once", "delay": "1m"},
        payload={"test": "data"}
    )
    
    next_exec = await scheduler.acknowledge_task(
        task_id=task_id,
        status="success",
        execution_time_ms=100
    )
    
    # One-time task should return None
    assert next_exec is None
    
    # Check execution history
    history = await scheduler.db.get_execution_history(task_id)
    assert len(history) == 1
    assert history[0]["status"] == "success"

@pytest.mark.asyncio
async def test_recurring_task(scheduler):
    """Test recurring task"""
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "recurring", "delay": "1m", "repeat": {"interval": "1h", "times": 3}},
        payload={"test": "data"}
    )
    
    # Acknowledge first execution
    next_exec = await scheduler.acknowledge_task(
        task_id=task_id,
        status="success"
    )
    
    # Should have next execution
    assert next_exec is not None

@pytest.mark.asyncio
async def test_cancel_task(scheduler):
    """Test task cancellation"""
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "once", "delay": "1m"},
        payload={"test": "data"}
    )
    
    await scheduler.cancel_task(task_id)
    
    task = await scheduler.db.get_task(task_id)
    assert task["status"] == "cancelled"

@pytest.mark.asyncio
async def test_restore_state(scheduler):
    """Test state restoration"""
    # Schedule a task
    task_id = await scheduler.schedule_task(
        schedule_type="test_task",
        when={"type": "once", "delay": "1h"},
        payload={"test": "data"}
    )
    
    # Restore state
    await scheduler.restore_state()
    
    # Task should still be active
    task = await scheduler.db.get_task(task_id)
    assert task["status"] == "active"

