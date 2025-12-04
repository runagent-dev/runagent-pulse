# RunAgent Pulse Python SDK

## Installation

```bash
pip install runagent-pulse
```

## Quick Start

```python
from runagent_pulse import PulseClient

# Initialize client
pc = PulseClient(
    server_url="http://localhost:8000",
    api_key="optional_key"
)

# Schedule a task
task = pc.schedule(
    schedule_type="send_mail",
    when="in 5 minutes",
    payload={"to": "user@example.com", "body": "Hello"}
)

print(f"Task ID: {task.id}")
```

## Basic Usage

### Scheduling Tasks

```python
# ISO 8601 timestamp
task = pc.schedule("send_mail", "2024-12-05T14:30:00Z", {"to": "user@example.com"})

# Relative time
task = pc.schedule("send_mail", "in 5 minutes", {"to": "user@example.com"})

# Natural language
task = pc.schedule("send_mail", "tomorrow at 2pm", {"to": "user@example.com"})

# Cron expression
task = pc.schedule("send_mail", {"type": "cron", "cron": "0 9 * * *"}, {"to": "user@example.com"})

# Recurring task
task = pc.schedule(
    "send_mail",
    {"type": "recurring", "delay": "5m", "repeat": {"interval": "1h", "times": 5}},
    {"to": "user@example.com"}
)
```

### Task Management

```python
# Get task details
task_details = task.get_details()

# Pause task
task.pause()

# Resume task
task.resume()

# Cancel task
task.cancel()

# Get execution history
history = task.get_history(limit=10)
for execution in history:
    print(f"{execution['executed_at_iso']}: {execution['status']}")
```

### Polling for Tasks

```python
# Manual polling
result = pc.poll(["send_mail", "order_food"], limit=10)
for task in result["tasks"]:
    print(f"Due task: {task['task_id']}")
```

## Callback-Based Execution

```python
from runagent_pulse import PulseClient

pc = PulseClient(server_url="http://localhost:8000")

# Register callback
@pc.on_trigger("send_mail")
def handle_send_mail(to: str, body: str, task_id: str, scheduled_for: str):
    """Automatically called when task is due"""
    print(f"Sending email to {to}: {body}")
    # Send email logic here
    return {"status": "sent"}

@pc.on_trigger("order_food")
def handle_order_food(name: str, count: int, task_id: str):
    print(f"Ordering {count}x {name}")
    return {"status": "ordered"}

# Start polling (blocking)
pc.start_polling(
    poll_interval=5,  # seconds
    schedule_types=["send_mail", "order_food"]
)

# Or run in background thread
pc.start_polling(daemon=True)
```

## Task Builder

Fluent interface for task creation:

```python
from runagent_pulse import TaskBuilder

task = (
    TaskBuilder(pc)
    .type("send_mail")
    .in_("5 minutes")
    .with_payload(to="user@example.com", body="Hello")
    .repeat(times=3, every="1 hour")
    .tag("urgent", "notification")
    .build()
)
```

## Batch Operations

```python
# Schedule multiple tasks
tasks = pc.schedule_batch([
    {"schedule_type": "task1", "when": "tomorrow", "payload": {...}},
    {"schedule_type": "task2", "when": "in 1 hour", "payload": {...}}
])
```

## Framework Integrations

### LangGraph

```python
from runagent_pulse.tools.langgraph import SchedulerTool

scheduler_tool = SchedulerTool(
    server_url="http://localhost:8000",
    api_key="optional_key",
    schedule_types={
        "send_mail": {
            "to": str,
            "body": str,
            "subject": str | None
        }
    }
)

# Register callbacks
@scheduler_tool.on_trigger("send_mail")
def send_mail_handler(to: str, body: str, subject: str = "No Subject"):
    # Implementation
    pass

# Use in LangGraph
from langgraph.prebuilt import create_react_agent

tools = [scheduler_tool.as_langgraph_tool()]
agent = create_react_agent(model, tools)
```

### CrewAI

```python
from runagent_pulse.tools.crewai import PulseSchedulerTool
from crewai import Agent, Task, Crew

scheduler_tool = PulseSchedulerTool(
    server_url="http://localhost:8000",
    schedule_types={
        "send_mail": {"to": str, "body": str}
    }
)

@scheduler_tool.on_trigger("send_mail")
def handle_mail(to: str, body: str):
    pass

# Create agent
scheduler_agent = Agent(
    role="Task Scheduler",
    goal="Schedule tasks based on user requests",
    tools=[scheduler_tool],
    verbose=True
)

crew = Crew(agents=[scheduler_agent], tasks=[...])
```

## Error Handling

```python
from runagent_pulse import PulseClient
import requests

pc = PulseClient(server_url="http://localhost:8000")

try:
    task = pc.schedule("send_mail", "invalid_time", {"to": "user@example.com"})
except ValueError as e:
    print(f"Invalid schedule: {e}")
except requests.exceptions.RequestException as e:
    print(f"API error: {e}")
```

## Advanced Examples

### Recurring Daily Report

```python
task = pc.schedule(
    "daily_report",
    {"type": "cron", "cron": "0 9 * * *"},  # Daily at 9am
    {"report_type": "summary"}
)
```

### Task with Metadata

```python
task = pc.schedule(
    "send_mail",
    "in 1 hour",
    {"to": "user@example.com"},
    metadata={
        "created_by": "agent_123",
        "tags": ["urgent", "notification"],
        "priority": "high"
    }
)
```

### Conditional Execution

```python
@pc.on_trigger("process_order")
def handle_order(order_id: str, amount: float, task_id: str):
    if amount > 1000:
        # Schedule follow-up
        pc.schedule(
            "send_notification",
            "in 1 day",
            {"type": "high_value_order", "order_id": order_id}
        )
    return {"status": "processed"}
```

