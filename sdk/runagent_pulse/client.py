"""
RunAgent Pulse Client
Python SDK for interacting with RunAgent Pulse server
"""
import logging
import os
import requests
import time
import threading
from typing import Optional, Dict, List, Callable, Any
from datetime import datetime
import json

from runagent_pulse.time import TimeParser
from runagent_pulse.contracts import (
    ScheduleTaskResponse,
    ListTasksResponse,
    CancelTaskResponse,
    GetTaskDetailsResponse,
)

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

        # Lightweight debug switch (set RUNAGENT_PULSE_DEBUG=1)
        self._debug = os.getenv("RUNAGENT_PULSE_DEBUG", "").lower() in (
            "1", "true", "yes", "on", "debug"
        )
        self.logger = logging.getLogger("runagent_pulse.client")
        if self._debug:
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
            redacted_headers = {
                k: v for k, v in self.headers.items()
                if k.lower() != "authorization"
            }
            self.logger.debug(
                "RUNAGENT_PULSE_DEBUG enabled; server=%s headers=%s",
                self.server_url,
                redacted_headers,
            )
        
        self.time_parser = TimeParser()
        self.callbacks: Dict[str, List[tuple[Callable, bool]]] = {}
        self.polling = False
        self.poll_thread: Optional[threading.Thread] = None
        self.worker_id = f"worker-{int(time.time())}-{threading.get_ident()}"
        
    def schedule(self, schedule_type: str, when: Any, payload: Dict[str, Any],
                repeat: Optional[Dict[str, Any]] = None,
                metadata: Optional[Dict[str, Any]] = None,
                webhook_url: Optional[str] = None,
                webhook_timeout: Optional[int] = None,
                webhook_retries: Optional[int] = None) -> PulseTask:
        """
        Schedule a task
        
        Args:
            schedule_type: Type of task (e.g., "send_mail")
            when: Time specification (ISO string, dict, or natural language)
            payload: Task payload data
            repeat: Optional repeat configuration
            metadata: Optional metadata
            webhook_url: Optional webhook target URL
            webhook_timeout: Optional timeout seconds (default server-side)
            webhook_retries: Optional retry attempts (default server-side)
            
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
                "metadata": metadata,
                "webhook_url": webhook_url,
                "webhook_timeout": webhook_timeout,
                "webhook_retries": webhook_retries,
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
    
    def claim_task(self, task_id: str) -> Optional[str]:
        """
        Try to claim a task
        
        Returns:
            execution_id if claimed successfully, None otherwise
        """
        try:
            response = requests.post(
                f"{self.server_url}/tasks/{task_id}/claim",
                headers=self.headers,
                json={"worker_id": self.worker_id}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("execution_id")
            return None
        except requests.exceptions.RequestException:
            return None

    def acknowledge(self, task_id: str, status: str = "success",
                   execution_time_ms: Optional[int] = None,
                   error: Optional[str] = None,
                   execution_id: Optional[str] = None) -> Optional[str]:
        """
        Acknowledge task execution
        
        Args:
            task_id: Task ID
            status: Execution status (success/failed)
            execution_time_ms: Execution time in milliseconds
            error: Error message if failed
            execution_id: Execution ID from claim (optional, will be extracted if not provided)
        
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
                "worker_id": self.worker_id,
                "execution_id": execution_id
            }
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("next_execution")
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task details"""
        response = requests.get(
            f"{self.server_url}/tasks/{task_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def update_task(self, task_id: str, updates: dict):
        """Update task (pause, resume, modify)"""
        response = requests.patch(
            f"{self.server_url}/tasks/{task_id}",
            headers=self.headers,
            json=updates
        )
        response.raise_for_status()
        return response.json()
    
    def delete_task(self, task_id: str):
        """Cancel/delete task"""
        response = requests.delete(
            f"{self.server_url}/tasks/{task_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_tasks(self, status: Optional[str] = None, schedule_type: Optional[str] = None,
                   start_time: Optional[int] = None, end_time: Optional[int] = None,
                   limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """List tasks with filters"""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if schedule_type:
            params["schedule_type"] = schedule_type
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        
        response = requests.get(
            f"{self.server_url}/tasks",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_task_history(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history for a task"""
        response = requests.get(
            f"{self.server_url}/tasks/{task_id}/history",
            headers=self.headers,
            params={"limit": limit}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("history", [])
    
    def schedule_agent(
        self,
        agent_id: str,
        entrypoint_tag: str,
        when: Any,
        params: Dict[str, Any],
        callback_url: Optional[str] = None,
        user_id: Optional[str] = None,
        persistent_memory: bool = False,
        executor_type: Optional[str] = None,
        local: Optional[bool] = None,
        repeat: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_host: Optional[str] = None,
        agent_port: Optional[int] = None,
    ) -> PulseTask:
        """
        Schedule agent execution
        
        Args:
            agent_id: Agent ID (for serverless) or module name (for local)
            entrypoint_tag: Agent entrypoint to execute
            when: When to execute ("in 5 minutes", "tomorrow at 9am", "now", cron)
            params: Parameters to pass to agent (dict that matches agent function args)
            callback_url: Optional webhook URL to POST result to
            user_id: Optional user ID for persistent memory
            persistent_memory: Enable persistent memory for agent
            executor_type: Executor type ("serverless", "local", or None for auto)
            local: If True, use RunAgent local execution (RunAgentClient with local=True).
                   If False, use RunAgent serverless (RunAgentClient with local=False).
                   If None, use executor_type to determine behavior.
            repeat: Optional repeat configuration for recurring execution.
                   Format: {"interval": "30s", "times": None} for infinite,
                   or {"interval": "30s", "times": 5} for limited repetitions.
                   Examples: "30s", "1m", "5m", "1h", "1d"
            metadata: Optional metadata
            
        Returns:
            PulseTask instance
            
        Example:
            # Schedule agent to run every 30 seconds
            task = pulse.schedule_agent(
                agent_id="your-agent-id",
                entrypoint_tag="your-entrypoint",
                when="now",
                params={"prompt": "Hello"},
                repeat={"interval": "30s", "times": None}  # Infinite
            )
        """
        payload = {
            "agent_id": agent_id,
            "entrypoint_tag": entrypoint_tag,
            "params": params,
            "user_id": user_id,
            "persistent_memory": persistent_memory,
        }

        if agent_host:
            payload["agent_host"] = agent_host
        if agent_port:
            payload["agent_port"] = agent_port
        
        # Add executor_type to payload if specified
        if executor_type:
            payload["executor_type"] = executor_type
        
        # Add local parameter to payload if specified
        if local is not None:
            payload["local"] = local
        
        # Merge metadata if provided
        if metadata:
            payload_metadata = metadata.copy()
        else:
            payload_metadata = {}
        
        # Store executor_type in metadata as well for backward compatibility
        if executor_type:
            payload_metadata["executor_type"] = executor_type
        
        # Store local parameter in metadata for the worker to use
        if local is not None:
            payload_metadata["local"] = local
        
        # Store callback_url in metadata for the worker to use
        if callback_url:
            payload_metadata["callback_url"] = callback_url

        if agent_host:
            payload_metadata["agent_host"] = agent_host
        if agent_port:
            payload_metadata["agent_port"] = agent_port
        
        return self.schedule(
            schedule_type="run_agent",
            when=when,
            payload=payload,
            repeat=repeat,
            metadata=payload_metadata,
            webhook_url=callback_url,  # Also set webhook_url for webhook worker compatibility
        )
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get result for a task
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict with status and result:
            - {"status": "pending"} if not yet executed
            - {"status": "completed", "result": {...}} when done
            - {"status": "failed", "error": "..."} if failed
        """
        response = requests.get(
            f"{self.server_url}/tasks/{task_id}/result",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def schedule_http(
        self,
        url: str,
        method: str = "POST",
        when: Any = "now",
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PulseTask:
        """
        Schedule an HTTP request to be executed at a specific time
        
        Args:
            url: Target URL to hit
            method: HTTP method (GET, POST, PUT, DELETE, etc.) - defaults to POST
            when: When to execute ("in 5 minutes", "tomorrow at 9am", "now", cron, etc.)
            body: Request body (dict will be JSON-encoded)
            headers: Optional HTTP headers to include in the request
            timeout: Optional timeout in seconds (default: 30)
            callback_url: Optional webhook URL to POST result to
            metadata: Optional metadata
            
        Returns:
            PulseTask instance
            
        Example:
            # Schedule morning routine
            task = pulse.schedule_http(
                url="http://localhost:5000/agents/morning-routine",
                method="POST",
                when="daily at 9am",
                body={"user": "sawradip"},
                headers={"Authorization": "Bearer my-secret-token"}
            )
        """
        payload = {
            "url": url,
            "method": method.upper(),
        }
        
        if body is not None:
            payload["body"] = body
        
        if headers:
            payload["headers"] = headers
        
        if timeout:
            payload["timeout"] = timeout
        
        # Merge metadata
        payload_metadata = metadata.copy() if metadata else {}
        
        # Store callback_url in metadata for the worker to use
        if callback_url:
            payload_metadata["callback_url"] = callback_url
        
        return self.schedule(
            schedule_type="http_request",
            when=when,
            payload=payload,
            metadata=payload_metadata,
            webhook_url=callback_url,  # Also set webhook_url for webhook worker compatibility
        )

    def call_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a catalog-exposed tool over HTTP.
        """
        if self._debug:
            redacted_headers = {
                k: v for k, v in self.headers.items()
                if k.lower() != "authorization"
            }
            self.logger.debug(
                "Calling tool '%s' -> %s/tools/%s | payload=%s | headers=%s",
                name,
                self.server_url,
                name,
                kwargs,
                redacted_headers,
            )
        response = requests.post(
            f"{self.server_url}/tools/{name}",
            headers=self.headers,
            json=kwargs,
        )
        if self._debug:
            self.logger.debug(
                "Tool '%s' response status=%s body=%s",
                name,
                response.status_code,
                response.text,
            )
        response.raise_for_status()
        return response.json()
    
    def on_trigger(self, schedule_type: str, allow_extra: bool = False):
        """
        Register callback for schedule type
        
        Args:
            schedule_type: Type of task to listen for
            allow_extra: If True, passes task_id and scheduled_for to callback.
                        If False (default), only payload fields are passed.
        """
        def decorator(func: Callable):
            if schedule_type not in self.callbacks:
                self.callbacks[schedule_type] = []
            # Store callback as tuple (func, allow_extra)
            self.callbacks[schedule_type].append((func, allow_extra))
            return func
        return decorator
    
    def start_polling(self, schedule_types: Optional[List[str]] = None, poll_interval: int = 5):
        """
        Start polling for tasks
        
        Args:
            schedule_types: Optional list of schedule types to poll for.
                          If None, automatically uses all registered trigger types.
            poll_interval: Seconds between polls (default: 5)
        """
        if self.polling:
            return
        
        # If no schedule types specified, use all registered trigger types
        if schedule_types is None:
            schedule_types = list(self.callbacks.keys())
            if not schedule_types:
                raise ValueError("No schedule types to poll. Register triggers with @client.on_trigger() first, or pass schedule_types explicitly.")
        
        self.polling = True
        self.poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(poll_interval, schedule_types),
            daemon=True
        )
        self.poll_thread.start()

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
                    execution_id = self.claim_task(task_id)
                    if not execution_id:
                        continue

                    # Call each callback
                    for callback_info in callbacks:
                        callback, allow_extra = callback_info

                        # Prepare callback arguments
                        callback_kwargs = payload.copy()
                        # Add extra metadata only if allowed
                        if allow_extra:
                            callback_kwargs["task_id"] = task_id
                            callback_kwargs["scheduled_for"] = task.get("scheduled_for")

                        try:
                            start_time = time.time()
                            result = callback(**callback_kwargs)
                            execution_time = int((time.time() - start_time) * 1000)
                            self.acknowledge(task_id, "success", execution_time_ms=execution_time, execution_id=execution_id)
                        except Exception as e:
                            logger.error(f"Task {task_id} failed: {e}")
                            self.acknowledge(task_id, "failed", error=str(e), execution_id=execution_id)
                
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
                metadata=task_spec.get("metadata"),
                webhook_url=task_spec.get("webhook_url"),
                webhook_timeout=task_spec.get("webhook_timeout"),
                webhook_retries=task_spec.get("webhook_retries"),
            )
            results.append(task)
        return results



