"""
LangGraph integration for RunAgent Pulse
"""
from typing import Dict, Any, Optional, Callable, List
from pydantic import BaseModel, Field
import inspect

try:
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import CallbackManagerForToolRun
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseTool = object
    CallbackManagerForToolRun = None

from runagent_pulse.client import PulseClient

class SchedulerTool(BaseTool):
    """LangGraph tool for scheduling tasks"""
    
    name: str = "schedule_task"
    description: str = """Schedule a task to be executed at a specific time. 
    Use this tool when you need to schedule actions like sending emails, 
    reminders, or any time-based operations.
    
    Examples:
    - "Schedule an email to user@example.com tomorrow at 2pm"
    - "Send a reminder in 5 minutes"
    - "Schedule a daily report at 9am"
    """
    
    client: PulseClient
    schedule_types: Dict[str, Dict[str, type]]
    callbacks: Dict[str, List[Callable]]
    
    def __init__(self, server_url: str, api_key: Optional[str] = None,
                 schedule_types: Optional[Dict[str, Dict[str, type]]] = None,
                 **kwargs):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("langgraph is not installed. Install with: pip install runagent-pulse[langgraph]")
        
        client = PulseClient(server_url, api_key)
        schedule_types = schedule_types or {}
        callbacks = {}
        
        super().__init__(
            client=client,
            schedule_types=schedule_types,
            callbacks=callbacks,
            **kwargs
        )
    
    def _run(
        self,
        schedule_type: str,
        when: str,
        **kwargs: Any,
    ) -> str:
        """Execute the tool"""
        try:
            # Build payload from kwargs
            payload = {}
            for key, value in kwargs.items():
                if key not in ["schedule_type", "when"]:
                    payload[key] = value
            
            # Schedule the task
            task = self.client.schedule(
                schedule_type=schedule_type,
                when=when,
                payload=payload
            )
            
            return f"Task scheduled successfully. Task ID: {task.task_id}. Scheduled for: {when}"
        except Exception as e:
            return f"Error scheduling task: {str(e)}"
    
    def as_langgraph_tool(self):
        """Return tool configured for LangGraph"""
        # Generate schema from schedule_types
        if self.schedule_types:
            # Create a dynamic tool with proper schema
            properties = {}
            required = ["schedule_type", "when"]
            
            # Add schedule_type enum
            properties["schedule_type"] = {
                "type": "string",
                "enum": list(self.schedule_types.keys()),
                "description": "Type of task to schedule"
            }
            
            # Add when field
            properties["when"] = {
                "type": "string",
                "description": "When to execute the task. Can be ISO 8601, relative time (e.g., 'in 5 minutes', 'tomorrow at 2pm'), or cron expression"
            }
            
            # Add payload fields based on schedule types
            # For simplicity, we'll use a generic payload field
            # In a more sophisticated implementation, we'd generate specific schemas per type
            properties["payload"] = {
                "type": "object",
                "description": "Task payload data"
            }
            
            tool_schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
            # Create tool with schema
            class DynamicSchedulerTool(BaseTool):
                name: str = "schedule_task"
                description: str = self.description
                
                def _run(self, schedule_type: str, when: str, payload: Optional[Dict] = None, **kwargs) -> str:
                    # Merge payload and kwargs
                    task_payload = payload or {}
                    task_payload.update(kwargs)
                    
                    task = self.client.schedule(
                        schedule_type=schedule_type,
                        when=when,
                        payload=task_payload
                    )
                    return f"Task scheduled. ID: {task.task_id}"
            
            tool = DynamicSchedulerTool()
            tool.client = self.client
            return tool
        
        return self
    
    def on_trigger(self, schedule_type: str):
        """Register callback for schedule type"""
        def decorator(func: Callable):
            if schedule_type not in self.callbacks:
                self.callbacks[schedule_type] = []
            self.callbacks[schedule_type].append(func)
            # Also register with client
            self.client.on_trigger(schedule_type)(func)
            return func
        return decorator


