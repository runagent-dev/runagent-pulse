"""
RunAgent Pulse Client
Python SDK for interacting with RunAgent Pulse server
"""
import requests
import time
import threading
from typing import Optional, Dict, List, Callable, Any
from datetime import datetime
import json

from runagent_pulse.time_parser import TimeParser

class PulseTask:
    """Wrapper for a scheduled task"""
    
    def __init__(self, task_id: str, client: 'PulseClient'):
        self.task_id = task_id
        self.client = client
        self.id = task_id  # Alias for compatibility
    
    def pause(self):
        """Pause the task"""
        self.client.update_task(self.task_id, {"status": "paused"})
    
    def resume(self):
        """Resume the task"""
        self.client.update_task(self.task_id, {"status": "active"})
    
    def cancel(self):
        """Cancel the task"""
        self.client.delete_task(self.task_id)
    
    def get_details(self) -> Dict[str, Any]:
        """Get task details"""
        return self.client.get_task(self.task_id)
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history"""
        return self.client.get_task_history(self.task_id, limit=limit)

class PulseClient:
    """Main client for RunAgent Pulse"""
    
    def __init__(self, server_url: str, api_key: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self.headers["Content-Type"] = "application/json"
        
        self.time_parser = TimeParser()
        self.callbacks: Dict[str, List[Callable]] = {}
        self.polling = False
        self.poll_thread: Optional[threading.Thread] = None
        self.worker_id = f"worker-{int(time.time())}-{threading.get_ident()}"
        
    def schedule(self, schedule_type: str, when: Any, payload: Dict[str, Any],
                repeat: Optional[Dict[str, Any]] = None,
                metadata: Optional[Dict[str, Any]] = None) -> PulseTask:
        """
        Schedule a task
        
        Args:
            schedule_type: Type of task (e.g., "send_mail")
            when: Time specification (ISO string, dict, or natural language)
            payload: Task payload data
            repeat: Optional repeat configuration
            metadata: Optional metadata
            
        Returns:
            PulseTask instance
        """
        # Normalize 'when' to dict format
        when_dict = self._normalize_when(when)
        
        response = requests.post(
            f"{self.server_url}/tasks/schedule",
            headers=self.headers,
            json={
                "schedule_type": schedule_type,
                "when": when_dict,
                "payload": payload,
                "repeat": repeat,
                "metadata": metadata
            }
        )
        response.raise_for_status()
        
        data = response.json()
        return PulseTask(data["task_id"], self)
    
    def _normalize_when(self, when: Any) -> Dict[str, Any]:
        """Normalize when parameter to dict format"""
        if isinstance(when, dict):
            return when
        
        if isinstance(when, str):
            # Try to parse as ISO 8601
            try:
                from dateutil import parser as date_parser
                date_parser.parse(when)
                return {"type": "once", "time": when}
            except:
                # Natural language
                return {"type": "once", "natural": when}
        
        raise ValueError(f"Invalid 'when' format: {when}")
    
    def poll(self, schedule_types: List[str], limit: int = 10) -> Dict[str, Any]:
        """
        Poll for due tasks
        
        Args:
            schedule_types: List of schedule types to poll for
            limit: Maximum number of tasks to return
            
        Returns:
            Dict with 'tasks' and 'next_poll_at'
        """
        types_str = ",".join(schedule_types)
        response = requests.get(
            f"{self.server_url}/tasks/poll",
            headers=self.headers,
            params={"types": types_str, "limit": limit}
        )
        response.raise_for_status()
        
        if response.status_code == 304:
            return {"tasks": [], "next_poll_at": None}
        
        return response.json()
    
    def claim_task(self, task_id: str) -> bool:
        """
        Try to claim a task
        
        Returns:
            True if claimed successfully
        """
        try:
            response = requests.post(
                f"{self.server_url}/tasks/{task_id}/claim",
                headers=self.headers,
                json={"worker_id": self.worker_id}
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def acknowledge(self, task_id: str, status: str = "success",
                   execution_time_ms: Optional[int] = None,
                   error: Optional[str] = None) -> Optional[str]:
        """
        Acknowledge task execution
        
        Returns:
            Next execution time (ISO) or None
        """
        response = requests.post(
            f"{self.server_url}/tasks/{task_id}/ack",
            headers=self.headers,
            json={
                "status": status,
                "execution_time_ms": execution_time_ms,
                "error": error,
                "worker_id": self.worker_id
            }
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("next_execution")
    
    # ... (get_task, update_task, delete_task, list_tasks, get_task_history, on_trigger, start_polling methods remain same) ...

    def _poll_loop(self, poll_interval: int, schedule_types: List[str]):
        """Internal polling loop with exponential backoff"""
        import logging
        logger = logging.getLogger("runagent_pulse")
        
        current_interval = poll_interval
        max_interval = 30
        
        while self.polling:
            try:
                result = self.poll(schedule_types, limit=100)
                tasks = result.get("tasks", [])
                
                # Reset backoff on success
                current_interval = poll_interval
                
                for task in tasks:
                    task_id = task["task_id"]
                    schedule_type = task["schedule_type"]
                    payload = task["payload"]
                    
                    # Get callbacks for this type
                    callbacks = self.callbacks.get(schedule_type, [])
                    
                    if not callbacks:
                        continue
                    
                    # Try to claim the task
                    if not self.claim_task(task_id):
                        continue
                    
                    # Prepare callback arguments
                    callback_kwargs = payload.copy()
                    callback_kwargs["task_id"] = task_id
                    callback_kwargs["scheduled_for"] = task.get("scheduled_for")
                    
                    # Call each callback
                    for callback in callbacks:
                        try:
                            start_time = time.time()
                            result = callback(**callback_kwargs)
                            execution_time = int((time.time() - start_time) * 1000)
                            self.acknowledge(task_id, "success", execution_time_ms=execution_time)
                        except Exception as e:
                            logger.error(f"Task {task_id} failed: {e}")
                            self.acknowledge(task_id, "failed", error=str(e))
                
                time.sleep(current_interval)
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
                # Exponential backoff
                time.sleep(current_interval)
                current_interval = min(current_interval * 2, max_interval)
    
    def stop_polling(self):
        """Stop polling"""
        self.polling = False
        if self.poll_thread:
            self.poll_thread.join(timeout=5)
    
    def schedule_batch(self, tasks: List[Dict[str, Any]]) -> List[PulseTask]:
        """Schedule multiple tasks"""
        results = []
        for task_spec in tasks:
            task = self.schedule(
                schedule_type=task_spec["schedule_type"],
                when=task_spec["when"],
                payload=task_spec["payload"],
                repeat=task_spec.get("repeat"),
                metadata=task_spec.get("metadata")
            )
            results.append(task)
        return results


