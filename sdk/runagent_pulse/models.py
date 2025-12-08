"""
Shared Pydantic models for all RunAgent Pulse tools
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# Schedule Task Parameters
class ScheduleTaskParams(BaseModel):
    """Parameters for scheduling a task"""
    schedule_type: str = Field(
        ...,
        description="Type of task to schedule (e.g., 'send_email', 'generate_report', 'webhook_call')",
        examples=["send_email", "data_sync", "report_generation"]
    )
    when: str = Field(
        ...,
        description="When to execute the task. Supports natural language, cron expressions, and ISO timestamps",
        examples=["tomorrow at 2pm", "0 9 * * 1-5", "in 30 minutes", "2024-12-25T00:00:00Z"]
    )
    payload: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Task-specific data and configuration parameters",
        examples=[{"to": "user@example.com", "subject": "Meeting reminder", "body": "Don't forget our meeting"}]
    )
    repeat: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration for recurring tasks",
        examples=[
            {"interval": "1 hour", "times": 5},
            {"cron": "0 */4 * * *"}  # Every 4 hours
        ]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for task organization and filtering",
        examples=[{"priority": "high", "tags": ["urgent", "client"], "project": "Q4_campaign"}]
    )
    webhook_url: Optional[str] = Field(
        None,
        description="URL to call when task completes (successful or failed)",
        examples=["https://api.example.com/webhooks/task-complete"]
    )
    webhook_timeout: Optional[int] = Field(
        30, ge=1, le=300,
        description="Seconds to wait for webhook response before timing out",
        examples=[30, 60, 120]
    )
    webhook_retries: Optional[int] = Field(
        3, ge=0, le=10,
        description="Number of webhook retry attempts on failure",
        examples=[0, 3, 5]
    )

# List Tasks Parameters
class ListTasksParams(BaseModel):
    """Parameters for listing tasks"""
    status: Optional[str] = Field(
        None,
        description="Filter tasks by status",
        examples=["active", "paused", "completed", "failed"]
    )
    schedule_type: Optional[str] = Field(
        None,
        description="Filter tasks by schedule type",
        examples=["send_email", "webhook_call", "data_sync"]
    )
    limit: int = Field(
        10, ge=1, le=1000,
        description="Maximum number of tasks to return",
        examples=[10, 50, 100]
    )
    offset: int = Field(
        0, ge=0,
        description="Number of tasks to skip (for pagination)",
        examples=[0, 10, 20]
    )

# Cancel Task Parameters
class CancelTaskParams(BaseModel):
    """Parameters for cancelling a task"""
    task_id: str = Field(
        ...,
        description="Unique identifier of the task to cancel",
        examples=["task_123456", "abc-def-ghi-123"]
    )

# Get Task Details Parameters
class GetTaskDetailsParams(BaseModel):
    """Parameters for getting task details"""
    task_id: str = Field(
        ...,
        description="Unique identifier of the task to retrieve",
        examples=["task_123456", "abc-def-ghi-123"]
    )

# Update Task Parameters
class UpdateTaskParams(BaseModel):
    """Parameters for updating a task"""
    task_id: str = Field(
        ...,
        description="Unique identifier of the task to update",
        examples=["task_123456", "abc-def-ghi-123"]
    )
    status: Optional[str] = Field(
        None,
        description="New status for the task",
        examples=["active", "paused"]
    )
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated task payload data"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata"
    )
