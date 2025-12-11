# Agent Scheduling Guide

This guide explains how to schedule agent executions via RunAgent Pulse. Pulse supports multiple execution backends:
- **Serverless**: Execute agents via RunAgent Serverless (default)
- **Local**: Execute agents locally without RunAgent Serverless

## Overview

RunAgent Pulse can schedule and execute agents deployed on RunAgent Serverless. The system supports two modes:

1. **Callback Mode**: Results are POSTed to a webhook URL
2. **Polling Mode**: Results are stored and can be retrieved via API

## Architecture

```
Developer Script → Pulse (schedule) → Wait for time → Execute via Serverless → 
Receive result → POST to webhook handler → Store/log result
```

### Components

- **Pulse Scheduler**: Schedules agent executions, triggers them at specified times
- **Agent Executor Worker**: Background worker that executes agents using modular executors
- **Executors**: Modular execution backends (Serverless, Local)
- **Webhook Handler**: Receives execution results from Pulse, logs/stores them
- **RunAgent Serverless**: External system that executes agents in microVMs (optional)

## Setup

### 1. Start Services

```bash
docker-compose up -d
```

This starts:
- `runagent-pulse` on port 8000
- `runagent-webhook-handler` on port 3001

### 2. Environment Variables

Create a `.env` file:

```bash
PULSE_API_KEY=optional-api-key
PULSE_DEBUG=true

# Serverless executor (optional)
ENABLE_SERVERLESS_INTEGRATION=true
RUNAGENT_SERVERLESS_API_KEY=your-serverless-api-key

# Local executor (optional)
LOCAL_AGENT_PATH=/path/to/agents  # Path to local agent modules

# Default executor selection
DEFAULT_EXECUTOR=auto  # "auto", "serverless", or "local"
```

## Usage

### Basic Scheduling

#### Serverless Execution (Default)

```python
from runagent_pulse import PulseClient

pulse = PulseClient(server_url="http://localhost:8000")

# Schedule agent execution via RunAgent Serverless
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="in 5 minutes",
    params={
        "prompt": "Hello, world!",
        "user": "developer"
    },
    executor_type="serverless"  # or None for auto
)

print(f"Task ID: {task.task_id}")
```

#### Local Execution

```python
# Schedule agent execution locally
task = pulse.schedule_agent(
    agent_id="my_agent_module",  # Python module name
    entrypoint_tag="process_request",
    when="now",
    params={
        "input": "Hello, world!"
    },
    executor_type="local"
)

print(f"Task ID: {task.task_id}")
```

**Note**: For local execution, `agent_id` should be a Python module name that can be imported. The module should contain a function matching `entrypoint_tag`.

### Callback Mode

Schedule with a webhook URL to receive results automatically:

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="tomorrow at 9am",
    params={"prompt": "Generate a report"},
    # Use Docker service name (for callbacks from Pulse container)
    callback_url="http://webhook-handler:3001/results"
    # Or use VM IP for external access: http://<VM_IP>:3001/results
)

# Results will be POSTed to the callback URL
# Check logs: docker logs -f runagent-webhook-handler
# Check files: ./webhook-results/{task_id}.json
```

**Webhook URL Options:**
- `http://webhook-handler:3001/results` - Works for callbacks from Pulse container (same Docker network)
- `http://localhost:3001/results` - Works if calling from host machine
- `http://<VM_IP>:3001/results` - Works for external access (replace with your VM's IP)

### Polling Mode

Schedule without a callback and poll for results:

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="in 1 minute",
    params={"prompt": "Hello"}
)

# Poll for result
import time
while True:
    result = pulse.get_task_result(task.task_id)
    
    if result["status"] == "completed":
        print(f"Result: {result['result']}")
        break
    elif result["status"] == "failed":
        print(f"Failed: {result.get('error')}")
        break
    else:
        print(f"Status: {result['status']}")
        time.sleep(5)
```

## Parameters

### `schedule_agent()` Parameters

- `agent_id` (str): 
  - For serverless: RunAgent agent ID
  - For local: Python module name
- `entrypoint_tag` (str): Agent entrypoint to execute (function name)
- `when` (str): When to execute ("in 5 minutes", "tomorrow at 9am", "now", cron)
- `params` (dict): Parameters to pass to agent (matches agent function args)
- `callback_url` (str, optional): Webhook URL to POST result to
- `user_id` (str, optional): User ID for persistent memory (serverless only)
- `persistent_memory` (bool): Enable persistent memory for agent (serverless only)
- `executor_type` (str, optional): Executor type ("serverless", "local", or None for auto)
- `metadata` (dict, optional): Optional metadata

### `params` Mapping

The `params` dict is passed directly to the agent's entrypoint function. For example:

**Agno Agent:**
```python
params = {
    "prompt": "Hello",
    "user": "developer",
    "new_session": True
}
```

**LangGraph Agent:**
```python
params = {
    "input": {"message": "Hello"},
    "config": {"configurable": {"thread_id": "123"}}
}
```

**CrewAI Agent:**
```python
params = {
    "task": "Research topic X",
    "context": {}
}
```

## Result Format

### Callback Payload

When using callback mode, the webhook receives:

```json
{
  "task_id": "abc123",
  "execution_id": "exec456",
  "status": "success",
  "result": {...},
  "execution_time_ms": 1234,
  "timestamp": 1234567890
}
```

### Polling Response

When polling, `get_task_result()` returns:

```python
{
    "status": "completed",  # or "pending", "failed"
    "result": {...},        # Only if status is "completed"
    "execution_id": "...",  # Only if status is "completed"
    "error": "..."          # Only if status is "failed"
}
```

## Examples

### Example 1: Schedule with Callback

See `examples/schedule_agent_example.py`

### Example 2: Schedule and Poll

See `examples/schedule_and_poll_example.py`

### Example 3: Recurring Agent Execution

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="daily-report",
    when="now",
    params={"report_type": "daily"},
    repeat={"interval": "1d"},  # Every day
    callback_url="http://webhook-handler:3001/results"
)
```

## Error Handling

The system handles various error scenarios:

- **Timeout**: Agent execution timeout (10 minutes max)
- **Invalid Agent**: Agent ID or entrypoint not found
- **Network Failures**: Retries with exponential backoff
- **Callback Failures**: Result is still stored even if callback fails

## Monitoring

### Check Webhook Handler Logs

```bash
docker logs -f runagent-webhook-handler
```

### Check Pulse Logs

```bash
docker logs -f runagent-pulse
```

### View Results

```bash
# List result files
ls -la ./webhook-results/

# View specific result
cat ./webhook-results/{task_id}.json

# Or via API
curl http://localhost:3001/results/{task_id}
```

## Executor Types

### Serverless Executor

Executes agents via RunAgent Serverless SDK. Requires:
- `runagent` package installed
- `ENABLE_SERVERLESS_INTEGRATION=true`
- `RUNAGENT_SERVERLESS_API_KEY` set (optional)

### Local Executor

Executes agents locally by importing Python modules. Requires:
- Agent module available in Python path
- `LOCAL_AGENT_PATH` set (optional, for custom paths)

**Local Agent Structure:**

```python
# my_agent.py
def process(input: str, user: str):
    """Process input and return result"""
    return f"Processed: {input} for {user}"
```

Or as a package:

```
my_agent/
  __init__.py
  process.py  # Contains process() function
```

## Troubleshooting

### Agent Not Executing (Serverless)

1. Check that `ENABLE_SERVERLESS_INTEGRATION=true`
2. Verify `RUNAGENT_SERVERLESS_API_KEY` is set
3. Check Pulse logs for errors
4. Verify agent_id and entrypoint_tag are correct
5. Ensure `runagent` package is installed

### Agent Not Executing (Local)

1. Verify agent module can be imported: `python -c "import my_agent"`
2. Check that entrypoint function exists in module
3. Set `LOCAL_AGENT_PATH` if agents are in custom location
4. Check Pulse logs for import errors
5. Ensure agent module is in Python path

### Results Not Received

1. Check webhook-handler logs
2. Verify callback_url is accessible from Pulse container
3. Check network connectivity between services
4. Verify result storage: `./webhook-results/` directory

### Timeout Issues

- Default timeout is 10 minutes
- For longer-running agents, consider breaking into smaller tasks
- Check agent execution logs in RunAgent Serverless

## Advanced Usage

### Custom Metadata

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="your-entrypoint",
    when="in 5 minutes",
    params={"prompt": "Hello"},
    metadata={
        "priority": "high",
        "source": "scheduled-job"
    }
)
```

### Persistent Memory

Enable persistent memory to maintain conversation context:

```python
task = pulse.schedule_agent(
    agent_id="your-agent-id",
    entrypoint_tag="chat",
    when="now",
    params={"message": "Hello"},
    user_id="user123",
    persistent_memory=True
)
```

## Framework-Specific Examples

### Agno

```python
task = pulse.schedule_agent(
    agent_id="agno-agent-id",
    entrypoint_tag="agno_print_response",
    when="in 2 minutes",
    params={
        "prompt": "Tell me a joke",
        "user": "developer",
        "new_session": True
    }
)
```

### LangGraph

```python
task = pulse.schedule_agent(
    agent_id="langgraph-agent-id",
    entrypoint_tag="invoke",
    when="now",
    params={
        "input": {"message": "Hello"},
        "config": {"configurable": {"thread_id": "thread-123"}}
    }
)
```

### CrewAI

```python
task = pulse.schedule_agent(
    agent_id="crewai-agent-id",
    entrypoint_tag="kickoff",
    when="tomorrow at 9am",
    params={
        "task": "Research and write a report",
        "context": {}
    }
)
```

## API Reference

### `schedule_agent()`

Schedule an agent execution.

**Returns:** `PulseTask` instance

### `get_task_result(task_id)`

Get execution result for a task.

**Returns:** Dict with status and result

### `PulseTask` Methods

- `task.get_details()`: Get task details
- `task.get_history()`: Get execution history
- `task.cancel()`: Cancel the task
- `task.pause()`: Pause the task
- `task.resume()`: Resume the task

