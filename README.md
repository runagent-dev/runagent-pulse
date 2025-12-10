# RunAgent Pulse

> **Google calendar for your agent**

RunAgent Pulse is a lightweight, self-hosted scheduling service designed for AI agents and developers. It provides second-level precision task scheduling with a simple API and a callback-based execution model.

## Features

- **Agent-First Design**: Natural language scheduling ("tomorrow at 2pm").
- **Local-First**: Runs as a single Docker container with SQLite persistence.
- **Robust Execution**: "Claim" mechanism prevents duplicate execution in multi-worker environments.
- **Efficient Polling**: Smart caching and long-polling support.
- **RunAgent Serverless Integration**: Schedule and execute agents deployed on RunAgent Serverless with callback-based results.

## Installation

### Server

1. **Using Docker Compose**:

   ```yaml
   version: '3.8'
   services:
     pulse:
       build: .
       container_name: runagent-pulse
       ports:
         - "8000:8000"
       volumes:
         - ./pulse-data:/app/data
       environment:
         - PULSE_API_KEY=${PULSE_API_KEY:-}
         - ENABLE_SERVERLESS_INTEGRATION=true
         - RUNAGENT_SERVERLESS_API_KEY=${RUNAGENT_SERVERLESS_API_KEY:-}
       networks:
         - runagent-network
     
     webhook-handler:
       build: ./webhook-handler
       container_name: runagent-webhook-handler
       ports:
         - "3001:3001"
       volumes:
         - ./webhook-results:/app/results
       networks:
         - runagent-network
       depends_on:
         - pulse
   
   networks:
     runagent-network:
       driver: bridge
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

#### Scheduling Agent Executions

Pulse can schedule and execute agents deployed on RunAgent Serverless:

```python
# Schedule with callback
task = client.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="in 5 minutes",
    params={"prompt": "Hello, world!"},
    callback_url="http://webhook-handler:3001/results"
)

# Or poll for results
task = client.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="now",
    params={"prompt": "Hello"}
)

# Poll for result
result = client.get_task_result(task.task_id)
```

See [Agent Scheduling Guide](docs/AGENT_SCHEDULING.md) for detailed documentation.

### API Reference

#### `POST /tasks/schedule`
Schedule a new task.

#### `GET /tasks/poll`
Poll for due tasks.

#### `POST /tasks/{task_id}/claim`
Claim a task for execution (handled automatically by SDK).

#### `POST /tasks/{task_id}/ack`
Acknowledge task execution.

#### `GET /tasks/{task_id}/result`
Get execution result for a task (for agent executions).

## Architecture

Pulse uses a "claim" pattern for robust execution:
1. Workers poll for due tasks.
2. When a task is found, the worker attempts to **claim** it.
3. Only if the claim succeeds (atomic database update) does the worker execute the task.
4. After execution, the worker **acknowledges** the task (success/failure).

This ensures that even if multiple workers see the same task, only one will execute it.

### Server layout
- Configuration is centralized in `server/settings.py` and injected via `app.state` in the FastAPI app factory (`server/main.py`).
- HTTP routes are organized under `server/api/*` and share dependencies through `server/dependencies.py`.
- Background workers live in `server/workers/` and are started/stopped inside the FastAPI lifespan.
- Agent executors are modularized in `server/executors/` (serverless, local, etc.).
- Tool catalog and context management are in `server/tools/`.
- MCP server is in `server/mcp/` and mounted at `/mcp`.
- Catalog-driven tool endpoints live under `/tools/{name}` (from `server/api/tools.py`) and publish metadata at `/meta/tools` for discovery across HTTP, MCP, and framework adapters.

## Agent Scheduling

RunAgent Pulse can schedule and execute agents using modular executors:

- **Serverless Executor**: Execute agents via RunAgent Serverless (default)
- **Local Executor**: Execute agents locally without RunAgent Serverless

The system supports:

- **Callback Mode**: Results are automatically POSTed to a webhook URL
- **Polling Mode**: Results are stored and can be retrieved via API

### Quick Start

1. **Start services**:
   ```bash
   docker-compose up -d
   ```

2. **Schedule an agent**:
   
   **Serverless (default)**:
   ```python
   from runagent_pulse import PulseClient
   
   pulse = PulseClient(server_url="http://localhost:8000")
   task = pulse.schedule_agent(
       agent_id="your-agent-id",
       entrypoint_tag="your-entrypoint",
       when="in 2 minutes",
       params={"prompt": "Hello"},
       executor_type="serverless",  # or None for auto
       callback_url="http://webhook-handler:3001/results"
   )
   ```
   
   **Local**:
   ```python
   task = pulse.schedule_agent(
       agent_id="my_agent_module",  # Python module name
       entrypoint_tag="process",
       when="now",
       params={"input": "Hello"},
       executor_type="local"
   )
   ```

3. **Check results**:
   ```bash
   # View webhook handler logs
   docker logs -f runagent-webhook-handler
   
   # Or view result files
   cat ./webhook-results/{task_id}.json
   ```

See [docs/AGENT_SCHEDULING.md](docs/AGENT_SCHEDULING.md) for complete documentation.

### Environment Variables

```bash
# .env file
PULSE_API_KEY=optional-api-key
PULSE_DEBUG=true

# Serverless executor (optional)
ENABLE_SERVERLESS_INTEGRATION=true
RUNAGENT_SERVERLESS_API_KEY=your-serverless-api-key

# Local executor (optional)
LOCAL_AGENT_PATH=/path/to/agents

# Default executor
DEFAULT_EXECUTOR=auto  # "auto", "serverless", or "local"
```


