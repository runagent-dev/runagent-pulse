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
from runagent_pulse.time import TimeParser

DEBUG = os.getenv("PULSE_DEBUG", "false").lower() == "true"
logger = logging.getLogger("runagent_pulse.scheduler")

class Scheduler:
    def __init__(self, db: Database, time_parser: TimeParser):
        self.db = db
        self.time_parser = time_parser
        
    async def schedule_task(self, schedule_type: str, when: dict, payload: dict,
                           repeat: Optional[dict] = None, metadata: Optional[dict] = None,
                           webhook_url: Optional[str] = None,
                           webhook_timeout: Optional[int] = None,
                           webhook_retries: Optional[int] = None) -> str:
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
        
        # Merge metadata and attach webhook config if provided
        merged_metadata = metadata.copy() if metadata else {}
        if webhook_url:
            # Convert httpx.Url object back to string for JSON serialization
            webhook_url_str = str(webhook_url) if webhook_url else None
            merged_metadata["webhook_url"] = webhook_url_str
            merged_metadata["is_webhook"] = True
            merged_metadata["webhook_timeout"] = webhook_timeout or 30
            merged_metadata["webhook_retries"] = webhook_retries or 3
            merged_metadata.setdefault("webhook_attempts", 0)
        
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
            metadata=merged_metadata if merged_metadata else None,
            next_execution=next_execution
        )
        
        # Add to time bucket
        await self.db.add_to_time_bucket(next_execution, task_id)
        
        return task_id
    
    async def claim_task(self, task_id: str, worker_id: str) -> Optional[str]:
        """
        Claim a task for execution
        
        Args:
            task_id: Task ID
            worker_id: Worker ID
            
        Returns:
            execution_id if claimed successfully, None otherwise
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
        # Exclude tasks that should be expired (older than 1 minute)
        expired_threshold = current_time - 60
        due_tasks = []
        for task in tasks:
            # Get full task to check exact execution time
            full_task = await self.db.get_task(task["task_id"])
            if full_task and full_task["next_execution"]:
                # Only include if due and not expired
                if full_task["next_execution"] <= current_time and full_task["next_execution"] > expired_threshold:
                    due_tasks.append(task)
                    if len(due_tasks) >= limit:
                        break
        
        return due_tasks
    
    async def acknowledge_task(self, task_id: str, status: str,
                              execution_time_ms: Optional[int] = None,
                              error: Optional[str] = None,
                              worker_id: Optional[str] = None,
                              execution_id: Optional[str] = None) -> Optional[str]:
        """
        Acknowledge task execution and schedule next occurrence if recurring
        
        Returns:
            next_execution timestamp (ISO format) or None
        """
        if DEBUG:
            logger.debug(f"Acknowledging task {task_id}: status={status}, worker_id={worker_id}, execution_time_ms={execution_time_ms}, error={error}")
        
        task = await self.db.get_task(task_id)
        if not task:
            if DEBUG:
                logger.debug(f"Task {task_id} not found")
            raise ValueError(f"Task {task_id} not found")
        
        if DEBUG:
            logger.debug(f"Task {task_id} status: {task['status']}")

        # Handle tasks that are already in final states
        if task["status"] in ["completed", "cancelled", "paused"]:
            logger.warning(f"Ignoring acknowledgment for {task['status']} task {task_id}")
            if DEBUG:
                logger.debug(f"Task {task_id} is already {task['status']} - ignoring acknowledgment")
            return None  # No next execution for final state tasks

        if task["status"] not in ["active", "processing", "expired"]:
            if DEBUG:
                logger.debug(f"Task {task_id} has invalid status: {task['status']}")
            raise ValueError(f"Task {task_id} is not active, processing, or expired (status: {task['status']})")
            
        # Use provided execution_id or extract from metadata
        metadata = task.get("metadata") or {}
        if not execution_id:
            execution_id = metadata.get("current_execution_id")
        
        # Check if task is expired - if so, this might be a late ack
        is_expired = task["status"] == "expired"
        
        # If expired and we have execution_id, check if this execution exists
        if is_expired and execution_id:
            existing_execution = await self.db.get_execution_by_id(execution_id)
            if existing_execution and existing_execution["status"] == "expired":
                if DEBUG:
                    logger.debug(f"Late ack for expired execution {execution_id}, updating status")
                # This is a late ack - update the execution status
                await self.db.update_execution_status(execution_id, status)
                # Don't schedule next execution for expired tasks that get late ack
                return None
        
        executed_at = int(time.time())
        
        if DEBUG:
            logger.debug(f"Recording execution for task {task_id} with execution_id={execution_id}")
        
        # Record execution
        await self.db.record_execution(
            task_id=task_id,
            execution_id=execution_id,
            executed_at=executed_at,
            status=status,
            execution_time_ms=execution_time_ms,
            error=error
        )
        
        # Remove from current time bucket
        if task["next_execution"]:
            if DEBUG:
                logger.debug(f"Removing task {task_id} from time bucket {task['next_execution']}")
            await self.db.remove_from_time_bucket(task["next_execution"], task_id)

        # If webhook final failure was flagged, stop further scheduling
        if metadata.get("is_webhook") and metadata.get("webhook_final_failure") and status == "failed":
            await self.db.update_task(task_id, {
                "status": "failed",
                "metadata": metadata,
                "next_execution": None
            })
            return None
        
        # Calculate next execution
        schedule_config = task["schedule_config"]
        # Pass the scheduled time (next_execution) instead of completion time
        scheduled_time = task.get("next_execution", executed_at)
        # Add scheduled_time to config for calculate_next_execution to use
        schedule_config_with_time = schedule_config.copy()
        schedule_config_with_time["scheduled_time"] = scheduled_time
        
        if DEBUG:
            logger.debug(f"Calculating next execution for task {task_id} with config: {schedule_config_with_time}, scheduled_time={scheduled_time}")
        
        try:
            next_execution = self.time_parser.calculate_next_execution(
                schedule_config_with_time,
                executed_at
            )
            if DEBUG:
                logger.debug(f"Next execution calculated: {next_execution}")
        except Exception as e:
            if DEBUG:
                logger.debug(f"Error calculating next execution: {str(e)}", exc_info=True)
            raise
        
        if next_execution:
            if DEBUG:
                logger.debug(f"Updating task {task_id} with next_execution={next_execution}")
            
            # Update task with next execution
            await self.db.update_task(task_id, {
                "next_execution": next_execution,
                "last_execution": executed_at
            })
            
            # Update execution count if recurring
            if "repeat" in schedule_config:
                repeat = schedule_config["repeat"]
                if DEBUG:
                    logger.debug(f"Updating execution count for recurring task {task_id}. Repeat config: {repeat}")
                # Always increment execution_count for recurring tasks
                execution_count = repeat.get("execution_count", 0) + 1
                repeat["execution_count"] = execution_count

                await self.db.update_task(task_id, {
                    "schedule_config": schedule_config
                })

                # Check if max executions reached
                times = repeat.get("times")
                if times is not None and execution_count >= times:
                    if DEBUG:
                        logger.debug(f"Task {task_id} reached max executions ({times}), marking as completed")
                    await self.db.update_task(task_id, {"status": "completed"})
                    return None  # No more executions
            
            # Add to new time bucket
            if DEBUG:
                logger.debug(f"Adding task {task_id} to time bucket {next_execution}")
            await self.db.add_to_time_bucket(next_execution, task_id)
            
            # Return ISO format
            next_execution_iso = datetime.utcfromtimestamp(next_execution).isoformat() + "Z"
            if DEBUG:
                logger.debug(f"Task {task_id} acknowledged. Next execution: {next_execution_iso}")
            return next_execution_iso
        else:
            # No more executions - mark as completed
            if DEBUG:
                logger.debug(f"Task {task_id} has no more executions. Marking as completed.")
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
            # Add scheduled_time to config for calculate_next_execution
            scheduled_time = task.get("next_execution", current_time)
            schedule_config_with_time = schedule_config.copy()
            schedule_config_with_time["scheduled_time"] = scheduled_time
            next_execution = self.time_parser.calculate_next_execution(
                schedule_config_with_time,
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

    async def expire_unclaimed_tasks(self, max_age_seconds: int = 60):
        """
        Expire tasks that haven't been claimed within max_age_seconds
        
        Args:
            max_age_seconds: Maximum age in seconds before expiration (default: 60)
        """
        import uuid
        current_time = int(time.time())
        expired_tasks = await self.db.get_expired_tasks(current_time, max_age_seconds)
        
        if DEBUG:
            logger.debug(f"Found {len(expired_tasks)} tasks to expire")
        
        for task in expired_tasks:
            task_id = task["id"]
            schedule_config = task["schedule_config"]
            
            if DEBUG:
                logger.debug(f"Expiring task {task_id}")
            
            # Generate execution_id for tracking (even though never claimed)
            execution_id = str(uuid.uuid4())
            expired_at = current_time
            
            # Record as expired
            await self.db.record_execution(
                task_id=task_id,
                execution_id=execution_id,
                executed_at=task["next_execution"],  # Use scheduled time
                expired_at=expired_at,
                status="expired"
            )
            
            # Remove from time bucket
            if task["next_execution"]:
                await self.db.remove_from_time_bucket(task["next_execution"], task_id)
            
            # Increment execution_count if recurring
            if "repeat" in schedule_config:
                repeat = schedule_config["repeat"]
                if "execution_count" in repeat:
                    repeat["execution_count"] = repeat.get("execution_count", 0) + 1
                    await self.db.update_task(task_id, {
                        "schedule_config": schedule_config
                    })
            
            # Check if task should be completed
            when = schedule_config.get("when", {})
            when_type = when.get("type", "once")
            
            if when_type == "once":
                # One-time task: mark as expired
                await self.db.update_task(task_id, {"status": "expired"})
            elif when_type == "recurring":
                # Check if max executions reached
                repeat = schedule_config.get("repeat", {})
                times = repeat.get("times")
                execution_count = repeat.get("execution_count", 0)
                
                if times is not None and execution_count >= times:
                    # Max executions reached, mark as completed
                    await self.db.update_task(task_id, {"status": "completed"})
                else:
                    # Calculate next execution
                    schedule_config_with_time = schedule_config.copy()
                    schedule_config_with_time["scheduled_time"] = task["next_execution"]
                    next_execution = self.time_parser.calculate_next_execution(
                        schedule_config_with_time,
                        current_time
                    )
                    
                    if next_execution:
                        await self.db.update_task(task_id, {
                            "next_execution": next_execution,
                            "status": "active"  # Keep active for next execution
                        })
                        await self.db.add_to_time_bucket(next_execution, task_id)
                    else:
                        await self.db.update_task(task_id, {"status": "completed"})



