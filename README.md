# RunAgent Pulse

> **Google calendar for your agent**

RunAgent Pulse is a lightweight, self-hosted scheduling service designed for AI agents and developers. It provides second-level precision task scheduling with a simple API and a callback-based execution model.

## Features

- **Agent-First Design**: Natural language scheduling ("tomorrow at 2pm").
- **Local-First**: Runs as a single Docker container with SQLite persistence.
- **Robust Execution**: "Claim" mechanism prevents duplicate execution in multi-worker environments.
- **Efficient Polling**: Smart caching and long-polling support.

## Installation

### Server

1. **Using Docker Compose**:

   ```yaml
   version: '3.8'
   services:
     pulse:
       image: runagent/pulse:latest
       ports:
         - "8000:8000"
       volumes:
         - ./data:/app/data
       environment:
         - PULSE_API_KEY=your_secret_key
   ```

   Run: `docker-compose up -d`

2. **Running Locally (Python)**:

   ```bash
   cd server
   pip install -r requirements.txt
   python main.py
   ```

### Client SDK

```bash
pip install runagent-pulse
```

## Usage

### Python SDK

#### Initialization

```python
from runagent_pulse import PulseClient

client = PulseClient(
    server_url="http://localhost:8000",
    api_key="your_secret_key"
)
```

#### Scheduling Tasks

```python
# Schedule a one-time task
task = client.schedule(
    schedule_type="send_email",
    when="tomorrow at 9am",
    payload={
        "to": "user@example.com",
        "subject": "Meeting Reminder"
    }
)

# Schedule a recurring task
task = client.schedule(
    schedule_type="check_status",
    when="now",
    payload={"service": "api"},
    repeat={"interval": "5m"}  # Every 5 minutes
)
```

#### Handling Tasks (Worker)

```python
@client.on_trigger("send_email")
def send_email(to: str, subject: str, task_id: str, scheduled_for: str):
    print(f"Sending email to {to}: {subject}")
    # Logic to send email...
    # Return value is ignored, but exceptions mark task as failed

# Start polling in background
client.start_polling(poll_interval=5)

# Keep main thread alive
import time
while True:
    time.sleep(1)
```

### API Reference

#### `POST /tasks/schedule`
Schedule a new task.

#### `GET /tasks/poll`
Poll for due tasks.

#### `POST /tasks/{task_id}/claim`
Claim a task for execution (handled automatically by SDK).

#### `POST /tasks/{task_id}/ack`
Acknowledge task execution.

## Architecture

Pulse uses a "claim" pattern for robust execution:
1. Workers poll for due tasks.
2. When a task is found, the worker attempts to **claim** it.
3. Only if the claim succeeds (atomic database update) does the worker execute the task.
4. After execution, the worker **acknowledges** the task (success/failure).

This ensures that even if multiple workers see the same task, only one will execute it.


