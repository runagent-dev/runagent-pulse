<div align="center">

![RunAgent Pulse Logo](icon%20/icon.png)

**Google Calendar for Your AI Agents**


# What is RunAgent Pulse?

A lightweight, self-hosted scheduling service designed for AI agents and developers. Schedule agent executions with second-level precision, natural language scheduling, and seamless integration with RunAgent Serverless.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Overview

RunAgent Pulse is a powerful scheduling system that brings enterprise-grade task scheduling to AI agent workflows. Whether you're running agents on RunAgent Serverless or locally, Pulse provides a unified interface for scheduling, executing, and monitoring agent tasks with precision timing and robust execution guarantees.

### Key Features

- **Natural Language Scheduling**: Schedule tasks using natural language like "tomorrow at 2pm" or "every 30 seconds"
- **RunAgent Serverless Integration**: Seamlessly schedule and execute agents deployed on RunAgent Serverless
- **Local Agent Support**: Execute agents running locally via `runagent serve`
- **Bring-Your-Own Endpoint**: Trigger any HTTP endpoint you expose; Pulse will schedule and call it for you (see `examples/schedule_http_example.py`)
- **MCP Server Integration**: Full Model Context Protocol support for AI agent frameworks
- **Modular Tools System**: Framework-specific tools for CrewAI, LangGraph, and MCP
- **Callback & Polling Modes**: Receive results via webhooks or poll for completion
- **Robust Execution**: Claim-based execution prevents duplicate runs in multi-worker environments
- **Self-Hosted**: Single Docker container with SQLite persistence

---

## Quick Start

### Installation

#### Using Docker Compose (Recommended)

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

Start the services:

```bash
docker-compose up -d
```

#### Python SDK Installation

```bash
pip install runagent-pulse
```

---

## RunAgent Serverless Integration

RunAgent Pulse makes scheduling agents on RunAgent Serverless incredibly simple. With just a few lines of code, you can schedule agent executions, set up recurring tasks, and receive results automatically.

> RunAgent Serverless docs and examples: https://github.com/runagent-dev/runagent

### Basic Serverless Scheduling

```python
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule an agent execution
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="in 5 minutes",
    params={
        "prompt": "Generate a daily report",
        "user": "developer"
    },
    executor_type="serverless",  # Default behavior
    callback_url="http://webhook-handler:3001/results"
)

print(f"Task scheduled: {task.task_id}")
```

### Recurring Agent Executions

Schedule agents to run automatically at regular intervals:

```python
# Run every 2 minutes, 5 times total
recurring_task = pulse.schedule_agent(
    agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
    entrypoint_tag="agno_print_response",
    when="in 1 minute",
    params={
        "prompt": "what is AI in one line?"
    },
    executor_type="serverless",
    repeat={"interval": "2m", "times": 5},
    callback_url="http://webhook-handler:3001/results"
)
```

### Callback Mode

Results are automatically POSTed to your webhook URL:

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="now",
    params={"prompt": "Hello, world!"},
    callback_url="http://your-webhook-server:3001/results"
)

# Results will be POSTed to your callback URL automatically
```

### Polling Mode

Store results and retrieve them via API:

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="now",
    params={"prompt": "Hello"}
)

# Poll for result
import time
while True:
    result = pulse.get_task_result(task.task_id)
    if result.get("status") == "completed":
        print(f"Result: {result.get('result')}")
        break
    time.sleep(2)
```

---

## Local Agent Execution

RunAgent Pulse can also execute agents running locally via `runagent serve`. This is perfect for development, testing, or when you want to keep execution on-premises.

### Starting a Local Agent Server

First, start your agent server:

```bash
runagent serve --host 0.0.0.0 /path/to/your/agent
```

The agent will start on a port (e.g., `8455`) and be accessible at `http://0.0.0.0:8455`.

### Scheduling Local Agents

```python
from runagent_pulse import PulseClient

pulse = PulseClient(server_url="http://localhost:8000")

# Schedule local agent execution
task = pulse.schedule_agent(
    agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
    entrypoint_tag="agno_print_response",
    when="in 1 minute",
    params={
        "prompt": "what is AI in one line?"
    },
    executor_type="local",
    agent_host="20.84.81.110",  # Your server IP or hostname
    agent_port=8455,            # Port where agent is running
    repeat={"interval": "2m", "times": 2},
    callback_url="http://webhook-handler:3001/results"
)
```

**Important**: When running Pulse in Docker, ensure:
- Your local agent server binds to `0.0.0.0` (not just `127.0.0.1`)
- The host/port is accessible from the Pulse container
- Use the server's IP address or hostname, not `localhost`

---

## Tools Integration

RunAgent Pulse provides framework-specific tools that integrate seamlessly with popular AI agent frameworks.

### CrewAI Integration

```python
from runagent_pulse.tools import crewai
from runagent_pulse import PulseClient
from crewai import Agent, Task, Crew

# Connect to Pulse
client = PulseClient("http://localhost:8000", api_key="your-key")

# Create CrewAI tools
schedule_tool = crewai.ScheduleTaskTool(client)
list_tool = crewai.ListTasksTool(client)
cancel_tool = crewai.CancelTaskTool(client)

# Use in CrewAI agent
agent = Agent(
    role="Task Scheduler",
    goal="Schedule and manage agent executions",
    tools=[schedule_tool, list_tool, cancel_tool],
    verbose=True
)

task = Task(
    description="Schedule a daily report agent to run every morning at 9am",
    agent=agent
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

### LangGraph Integration

```python
from runagent_pulse.tools import langgraph
from runagent_pulse import PulseClient

client = PulseClient("http://localhost:8000", api_key="your-key")

# Create LangGraph tools
tools = [
    langgraph.ScheduleTaskTool(client),
    langgraph.ListTasksTool(client),
    langgraph.CancelTaskTool(client),
    langgraph.GetTaskDetailsTool(client)
]

# Use in LangGraph workflow
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")
agent = create_react_agent(llm, tools)
```

### Available Tools

| Tool | Purpose | CrewAI | LangGraph | MCP |
|------|---------|--------|-----------|-----|
| `ScheduleTaskTool` | Schedule new tasks | ✅ | ✅ | ✅ |
| `ListTasksTool` | List/filter tasks | ✅ | ✅ | ✅ |
| `CancelTaskTool` | Cancel tasks | ✅ | ✅ | ✅ |
| `GetTaskDetailsTool` | Get task info + history | ✅ | ✅ | ✅ |

---

## MCP Server Integration

RunAgent Pulse includes a full Model Context Protocol (MCP) server that automatically exposes all scheduling tools to MCP-compatible clients.

### MCP Server Endpoint

The MCP server is mounted at `/mcp` on your Pulse instance:

```
http://localhost:8000/mcp
```

### Using with MCP Clients

```python
from fastmcp import Client as FastMCPClient

# Connect to Pulse MCP server
client = FastMCPClient(
    base_url="http://localhost:8000/mcp",
    name="pulse-client"
)

# List available tools
tools = client.list_tools()
print(f"Available tools: {[t.name for t in tools]}")

# Schedule a task via MCP
result = client.call_tool(
    name="schedule_task",
    arguments={
        "schedule_type": "run_agent",
        "when": {"type": "once", "natural": "in 5 minutes"},
        "payload": {
            "agent_id": "your-agent-id",
            "entrypoint_tag": "your-entrypoint",
            "params": {"prompt": "Hello from MCP!"}
        }
    }
)
```

### MCP Tool Discovery

All tools are automatically exposed via MCP with proper schemas:

```bash
# List tools
curl http://localhost:8000/mcp/tools/list

# Get tool schema
curl http://localhost:8000/mcp/tools/schedule_task
```

---

## Architecture

### Core Components

- **Scheduler**: Manages task scheduling with second-level precision using time buckets
- **Agent Executor Worker**: Background worker that executes agents using modular executors
- **Executors**: Pluggable execution backends (Serverless, Local)
- **MCP Server**: Model Context Protocol server for AI framework integration
- **Tool Catalog**: Centralized tool registry with framework-specific adapters

### Execution Flow

```
Developer Script → Pulse (schedule) → Wait for time → Execute via Executor → 
Receive result → POST to webhook handler → Store/log result
```

### Claim-Based Execution

Pulse uses a "claim" pattern for robust execution:

1. Workers poll for due tasks
2. When a task is found, the worker attempts to **claim** it (atomic database update)
3. Only if the claim succeeds does the worker execute the task
4. After execution, the worker **acknowledges** the task (success/failure)

This ensures that even if multiple workers see the same task, only one will execute it.

---

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Pulse Configuration
PULSE_API_KEY=optional-api-key
PULSE_DEBUG=true
PULSE_DB_PATH=/app/data/pulse.db
PULSE_TIMEZONE=UTC

# RunAgent Serverless Integration
ENABLE_SERVERLESS_INTEGRATION=true
RUNAGENT_SERVERLESS_API_KEY=your-serverless-api-key
RUNAGENT_BASE_URL=https://backend.run-agent.ai/

# Local Agent Execution (optional)
LOCAL_AGENT_PATH=/path/to/agents

# Default Executor Selection
DEFAULT_EXECUTOR=auto  # "auto", "serverless", or "local"

# Webhook Configuration
PULSE_WEBHOOK_TIMEOUT=30
PULSE_WEBHOOK_RETRIES=3
```

---

## API Reference

### Task Scheduling

#### `POST /tasks/schedule`

Schedule a new task.

**Request Body:**
```json
{
  "schedule_type": "run_agent",
  "when": {
    "type": "once",
    "natural": "in 5 minutes"
  },
  "payload": {
    "agent_id": "your-agent-id",
    "entrypoint_tag": "your-entrypoint",
    "params": {"prompt": "Hello"}
  },
  "metadata": {
    "executor_type": "serverless",
    "callback_url": "http://webhook-handler:3001/results"
  }
}
```

#### `GET /tasks/poll`

Poll for due tasks (high-performance endpoint with ETag support).

#### `POST /tasks/{task_id}/claim`

Claim a task for execution (handled automatically by SDK).

#### `POST /tasks/{task_id}/ack`

Acknowledge task execution.

#### `GET /tasks/{task_id}/result`

Get execution result for a task (for agent executions).

#### `GET /tasks/{task_id}/history`

Get execution history for a task.

### MCP Endpoints

#### `GET /mcp/tools/list`

List all available MCP tools.

#### `POST /mcp/tools/call`

Call an MCP tool.

---

## Examples

## Example 1: PaperFlow (arXiv paper scheduler)
### You can go the main repo of Paperflow [paper-flow](https://github.com/aritra741/paper-flow)

The `examples/test_paperflow.py` script shows a complete, copy‑paste workflow for scheduling a PaperFlow agent that searches arXiv for new papers on specific topics.

- **What it does**
  - **Daily mode**: Run your PaperFlow agent once per day at a specific time.
  - **Recurring mode**: Run the agent every N minutes/hours, a fixed number of times or indefinitely.

- **Setup**
  - **1. Configure Pulse + Serverless**: Start Pulse with Docker Compose (see **Quick Start**) and ensure `ENABLE_SERVERLESS_INTEGRATION=true` and `RUNAGENT_SERVERLESS_API_KEY` are set.
  - **2. Deploy your PaperFlow agent** on RunAgent Serverless and copy its `agent_id`.
  - **3. Edit the example**:
    - Open `examples/test_paperflow.py`
    - Set `AGENT_ID` to your deployed agent ID
    - Update `TOPICS` with the topics you care about (e.g. `"fine-tuning multimodal models"`)

- **Daily schedule (starting today)**

```python
from runagent_pulse import PulseClient

PULSE_SERVER_URL = "http://localhost:8000"
AGENT_ID = "<your-agent-id>"

TOPICS = [
    "fine-tuning multimodal models",
]

def schedule_daily():
    """Run once per day at 7:45 PM"""
    pulse = PulseClient(server_url=PULSE_SERVER_URL)

    task = pulse.schedule_agent(
        agent_id=AGENT_ID,
        entrypoint_tag="check_papers_async",
        # First run: natural language, parsed by Pulse
        when="today at 7:45pm",
        params={
            "topics": TOPICS,
            "max_results": 20,
            "days_back": 7,
            "verbose": True,
        },
        executor_type="serverless",
        user_id="paperflow_daily",
        persistent_memory=True,
        # Make it truly daily
        repeat={
            "interval": "1d",   # every 1 day
            "times": None       # infinite
        },
    )

    print(f"Scheduled PaperFlow daily: {task.task_id}")
```

- **Recurring schedule (every N minutes/hours)**

```python
def schedule_recurring(interval="10m", times=1):
    """Run at regular intervals (e.g., every 6 hours)"""
    pulse = PulseClient(server_url=PULSE_SERVER_URL)

    task = pulse.schedule_agent(
        agent_id=AGENT_ID,
        entrypoint_tag="check_papers_async",
        when="in 3 minute",  # start soon
        params={
            "topics": TOPICS,
            "max_results": 20,
            "days_back": 100,
            "verbose": True,
        },
        executor_type="serverless",
        user_id="paperflow_recurring",
        persistent_memory=True,
        repeat={
            "interval": interval,  # e.g. "10m", "2h", "1d"
            "times": times,        # None = infinite
        },
    )

    print(f"Scheduled PaperFlow every {interval}: {task.task_id}")
```

- **How to run it**

```bash
# Daily mode (once per day)
python examples/test_paperflow.py daily

# Recurring mode (every 6 hours, infinite)
python examples/test_paperflow.py recurring 6h

# Recurring mode (every 2 hours, 5 times)
python examples/test_paperflow.py recurring 2h 5
```

### Example 2: Daily Report Agent

```python
from runagent_pulse import PulseClient

pulse = PulseClient(server_url="http://localhost:8000")

# Schedule daily report every weekday at 9am
task = pulse.schedule_agent(
    agent_id="report-generator-agent",
    entrypoint_tag="generate_report",
    when="tomorrow at 9am",
    params={
        "report_type": "daily",
        "recipients": ["team@example.com"]
    },
    executor_type="serverless",
    repeat={
        "interval": "1d",
        "times": None  # Infinite
    },
    callback_url="http://webhook-handler:3001/results"
)
```

### Example 3: Monitoring Agent

```python
# Schedule monitoring agent every 5 minutes
monitoring_task = pulse.schedule_agent(
    agent_id="system-monitor-agent",
    entrypoint_tag="check_system",
    when="now",
    params={
        "services": ["api", "database", "cache"]
    },
    executor_type="serverless",
    repeat={"interval": "5m", "times": None},
    callback_url="http://alerting-service:3001/alerts"
)
```

---

## Documentation

- [Agent Scheduling Guide](docs/AGENT_SCHEDULING.md) - Complete guide to scheduling agents
- [Architecture Documentation](docs/ARCHITECTURE.md) - System architecture and design
- [Tools Documentation](INDIVIDUAL_TOOLS_README.md) - Framework-specific tools guide

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## License

MIT License - see LICENSE file for details.

---

<div align="center">

**Built with ❤️ for the AI agent community**

[Documentation](docs/) | [Examples](examples/) | [Issues](https://github.com/your-org/runagent-pulse/issues)

</div>
