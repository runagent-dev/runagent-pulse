"""
CrewAI integration for RunAgent Pulse
"""
from typing import Dict, Any, Optional, Callable, List

try:
    from crewai.tools import BaseTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object

from runagent_pulse.client import PulseClient

class PulseSchedulerTool(BaseTool):
    """CrewAI tool for scheduling tasks"""
    
    name: str = "schedule_task"
    description: str = """Schedule a task to be executed at a specific time. 
    Use this tool when you need to schedule actions like sending emails, 
    reminders, or any time-based operations.
    
    Examples:
    - "Schedule an email to user@example.com tomorrow at 2pm"
    - "Send a reminder in 5 minutes"
    - "Schedule a daily report at 9am"
    
    Parameters:
    - schedule_type: Type of task (e.g., 'send_mail', 'order_food')
    - when: When to execute (ISO 8601, relative time, or cron)
    - payload: Task data (dict with task-specific fields)
    """
    
    def __init__(self, server_url: str, api_key: Optional[str] = None,
                 schedule_types: Optional[Dict[str, Dict[str, type]]] = None):
        if not CREWAI_AVAILABLE:
            raise ImportError("crewai is not installed. Install with: pip install runagent-pulse[crewai]")
        
        self.client = PulseClient(server_url, api_key)
        self.schedule_types = schedule_types or {}
        self.callbacks: Dict[str, List[Callable]] = {}
        
        super().__init__()
    
    def _run(self, schedule_type: str, when: str, **payload: Any) -> str:
        """Execute the tool"""
        try:
            # Schedule the task
            task = self.client.schedule(
                schedule_type=schedule_type,
                when=when,
                payload=payload
            )
            
            return f"Task scheduled successfully. Task ID: {task.task_id}. Scheduled for: {when}"
        except Exception as e:
            return f"Error scheduling task: {str(e)}"
    
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

