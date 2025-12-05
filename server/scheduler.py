"""
Scheduling engine for RunAgent Pulse
Manages task scheduling, time buckets, and state restoration
"""
import time
import uuid
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from server.database import Database
from server.time_parser import TimeParser

DEBUG = os.getenv("PULSE_DEBUG", "false").lower() == "true"
logger = logging.getLogger("runagent_pulse.scheduler")

class Scheduler:
    def __init__(self, db: Database, time_parser: TimeParser):
        self.db = db
        self.time_parser = time_parser
        
    async def schedule_task(self, schedule_type: str, when: dict, payload: dict,
                           repeat: Optional[dict] = None, metadata: Optional[dict] = None) -> str:
        """
        Schedule a new task
        
        Returns:
            task_id
        """
        task_id = str(uuid.uuid4())
        created_at = int(time.time())
        
        if DEBUG:
            logger.debug(f"Scheduling task: schedule_type={schedule_type}, when={when}, repeat={repeat}")
        
        # If repeat is provided separately, convert when to recurring type
        if repeat and when.get("type") != "recurring":
            if DEBUG:
                logger.debug(f"Converting one-time schedule to recurring: when={when}, repeat={repeat}")
            
            # If when has "natural" language, parse it first to get a delay
            if "natural" in when:
                natural_time = when["natural"]
                if DEBUG:
                    logger.debug(f"Parsing natural language time: {natural_time}")
                
                # Special case: "now" means start immediately
                if natural_time.strip().lower() == "now":
                    if DEBUG:
                        logger.debug("Natural time is 'now', starting immediately")
                    when = {
                        "type": "recurring",
                        "repeat": repeat
                    }
                else:
                    # Parse natural language to get timestamp, then convert to delay
                    parsed_timestamp, _ = self.time_parser.parse({"type": "once", "natural": natural_time})
                    current_time = int(time.time())
                    delay_seconds = parsed_timestamp - current_time
                    if delay_seconds < 0:
                        delay_seconds = 0
                    if DEBUG:
                        logger.debug(f"Natural time parsed: timestamp={parsed_timestamp}, delay_seconds={delay_seconds}")
                    
                    # Convert to delay format (e.g., "5m")
                    if delay_seconds == 0:
                        # Start immediately - no delay field needed
                        when = {
                            "type": "recurring",
                            "repeat": repeat
                        }
                    else:
                        # Convert seconds to delay string
                        if delay_seconds < 60:
                            delay_str = f"{delay_seconds}s"
                        elif delay_seconds < 3600:
                            delay_str = f"{delay_seconds // 60}m"
                        elif delay_seconds < 86400:
                            delay_str = f"{delay_seconds // 3600}h"
                        else:
                            delay_str = f"{delay_seconds // 86400}d"
                        when = {
                            "type": "recurring",
                            "delay": delay_str,
                            "repeat": repeat
                        }
                if DEBUG:
                    logger.debug(f"Converted to recurring format: {when}")
            else:
                # Convert to recurring format, preserving time/delay fields
                when = {
                    "type": "recurring",
                    **{k: v for k, v in when.items() if k != "type"},
                    "repeat": repeat
                }
                if DEBUG:
                    logger.debug(f"Converted to recurring format (preserving fields): {when}")
        
        # Parse schedule
        schedule_config = {"when": when}
        
        if DEBUG:
            logger.debug(f"Parsing schedule config: {schedule_config}")
        
        # Calculate first execution time
        try:
            next_execution, recurrence = self.time_parser.parse(when)
            if DEBUG:
                logger.debug(f"Parsed schedule: next_execution={next_execution}, recurrence={recurrence}")
        except Exception as e:
            if DEBUG:
                logger.debug(f"Error parsing schedule: {str(e)}", exc_info=True)
            raise
        
        if recurrence:
            schedule_config["repeat"] = recurrence
        
        # Create task in database
        await self.db.create_task(
            task_id=task_id,
            schedule_type=schedule_type,
            created_at=created_at,
            payload=payload,
            schedule_config=schedule_config,
            metadata=metadata,
            next_execution=next_execution
        )
        
        # Add to time bucket
        await self.db.add_to_time_bucket(next_execution, task_id)
        
        return task_id
    
    async def claim_task(self, task_id: str, worker_id: str) -> bool:
        """
        Claim a task for execution
        
        Args:
            task_id: Task ID
            worker_id: Worker ID
            
        Returns:
            True if claimed successfully
        """
        return await self.db.claim_task(task_id, worker_id)
    
    async def get_due_tasks(self, schedule_types: List[str], current_time: int,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tasks that are due now or in the current minute
        
        Uses minute-level bucketing for efficiency
        """
        # Round to minute for bucketing
        current_minute = (current_time // 60) * 60
        next_minute = current_minute + 60
        
        # Get tasks from buckets in current minute range
        tasks = await self.db.get_due_tasks_from_buckets(
            start_time=current_minute,
            end_time=next_minute,
            schedule_types=schedule_types
        )
        
        # Filter to only tasks actually due (second-level precision)
        due_tasks = []
        for task in tasks:
            # Get full task to check exact execution time
            full_task = await self.db.get_task(task["task_id"])
            if full_task and full_task["next_execution"]:
                if full_task["next_execution"] <= current_time:
                    due_tasks.append(task)
                    if len(due_tasks) >= limit:
                        break
        
        return due_tasks
    
    async def acknowledge_task(self, task_id: str, status: str,
                              execution_time_ms: Optional[int] = None,
                              error: Optional[str] = None,
                              worker_id: Optional[str] = None) -> Optional[str]:
        """
        Acknowledge task execution and schedule next occurrence if recurring
        
        Returns:
            next_execution timestamp (ISO format) or None
        """
        task = await self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if task["status"] not in ["active", "processing"]:
            raise ValueError(f"Task {task_id} is not active or processing (status: {task['status']})")
            
        # Verify lock (Fencing Token)
        if worker_id:
            metadata = task.get("metadata") or {}
            locked_by = metadata.get("locked_by")
            if locked_by and locked_by != worker_id:
                raise ValueError(f"Lock mismatch: Task claimed by {locked_by}, but acknowledged by {worker_id}")
        
        executed_at = int(time.time())
        
        # Record execution
        await self.db.record_execution(
            task_id=task_id,
            executed_at=executed_at,
            status=status,
            execution_time_ms=execution_time_ms,
            error=error
        )
        
        # Remove from current time bucket
        if task["next_execution"]:
            await self.db.remove_from_time_bucket(task["next_execution"], task_id)
        
        # Calculate next execution
        schedule_config = task["schedule_config"]
        next_execution = self.time_parser.calculate_next_execution(
            schedule_config,
            executed_at
        )
        
        if next_execution:
            # Update task with next execution
            await self.db.update_task(task_id, {
                "next_execution": next_execution,
                "last_execution": executed_at
            })
            
            # Update execution count if recurring
            if "repeat" in schedule_config:
                repeat = schedule_config["repeat"]
                if "execution_count" in repeat:
                    repeat["execution_count"] = repeat.get("execution_count", 0) + 1
                    await self.db.update_task(task_id, {
                        "schedule_config": schedule_config
                    })
            
            # Add to new time bucket
            await self.db.add_to_time_bucket(next_execution, task_id)
            
            # Return ISO format
            return datetime.utcfromtimestamp(next_execution).isoformat() + "Z"
        else:
            # No more executions - mark as completed
            await self.db.update_task(task_id, {"status": "completed"})
            return None
    
    async def update_task(self, task_id: str, updates: dict):
        """Update task (pause, resume, modify)"""
        task = await self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Handle status changes
        if "status" in updates:
            new_status = updates["status"]
            old_status = task["status"]
            
            if new_status == "paused" and old_status == "active":
                # Remove from time bucket
                if task["next_execution"]:
                    await self.db.remove_from_time_bucket(task["next_execution"], task_id)
            elif new_status == "active" and old_status == "paused":
                # Re-add to time bucket
                if task["next_execution"]:
                    await self.db.add_to_time_bucket(task["next_execution"], task_id)
        
        # Update task
        await self.db.update_task(task_id, updates)
    
    async def cancel_task(self, task_id: str):
        """Cancel/delete task"""
        task = await self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Remove from time bucket
        if task["next_execution"]:
            await self.db.remove_from_time_bucket(task["next_execution"], task_id)
        
        # Mark as cancelled
        await self.db.update_task(task_id, {"status": "cancelled"})
    
    async def restore_state(self):
        """
        Restore state on server startup
        Rebuilds time buckets and handles missed tasks
        """
        current_time = int(time.time())
        
        # Get all active tasks
        active_tasks = await self.db.get_all_active_tasks()
        
        for task in active_tasks:
            schedule_config = task["schedule_config"]
            next_execution = self.time_parser.calculate_next_execution(
                schedule_config,
                current_time
            )
            
            if next_execution:
                # Update next execution time
                await self.db.update_task(task["id"], {
                    "next_execution": next_execution
                })
                
                # Add to time bucket
                await self.db.add_to_time_bucket(next_execution, task["id"])
            else:
                # No more executions - mark as completed
                await self.db.update_task(task["id"], {"status": "completed"})
    
    async def get_next_task_time(self, schedule_types: List[str], current_time: int) -> Optional[str]:
        """Get next task execution time for given types (ISO format)"""
        next_time = await self.db.get_next_task_time(schedule_types, current_time)
        if next_time:
            return datetime.utcfromtimestamp(next_time).isoformat() + "Z"
        return None



