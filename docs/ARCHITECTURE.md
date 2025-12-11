# RunAgent Pulse Architecture

## Overview

RunAgent Pulse uses a modular architecture with clear separation of concerns:

```
server/
├── api/              # HTTP API endpoints
├── executors/        # Agent execution backends (modular)
│   ├── base.py      # Base executor interface
│   ├── serverless.py # Serverless executor
│   ├── local.py     # Local executor
│   └── factory.py   # Executor factory
├── workers/         # Background workers
│   ├── agent_executor_worker.py  # Agent execution worker
│   └── __init__.py
├── database.py      # Database layer
├── scheduler.py     # Task scheduling
├── services.py     # Business logic
└── main.py         # Application entry point
```

## Modular Executors

### Base Executor Interface

All executors implement `BaseExecutor` which defines:

- `execute()`: Execute an agent
- `is_available()`: Check if executor is available
- `validate_params()`: Validate execution parameters

### Executor Types

#### Serverless Executor

Executes agents via RunAgent Serverless SDK.

**Requirements:**
- `runagent` package installed
- `ENABLE_SERVERLESS_INTEGRATION=true`
- Optional: `RUNAGENT_SERVERLESS_API_KEY`

**Usage:**
```python
executor = ServerlessExecutor(api_key="...")
result = await executor.execute(
    agent_id="agent-id",
    entrypoint_tag="entrypoint",
    params={"prompt": "Hello"}
)
```

#### Local Executor

Executes agents locally by importing Python modules.

**Requirements:**
- Agent module available in Python path
- Optional: `LOCAL_AGENT_PATH` for custom paths

**Usage:**
```python
executor = LocalExecutor(agent_path="/path/to/agents")
result = await executor.execute(
    agent_id="my_agent_module",
    entrypoint_tag="process",
    params={"input": "Hello"}
)
```

### Executor Factory

The `ExecutorFactory` manages executor instances and provides:

- `get_executor(type)`: Get executor by type
- `list_available()`: List available executor types

**Auto-selection:**
- If `type=None`, prefers serverless if available, otherwise local

## Worker Architecture

### Agent Executor Worker

The `AgentExecutorWorker` polls for tasks and executes them using the appropriate executor:

1. Polls for tasks with `schedule_type="run_agent"` or `"execute_agent"`
2. Claims tasks atomically
3. Selects executor based on task payload/metadata
4. Executes agent via executor
5. Stores results
6. POSTs to callback URL if provided
7. Acknowledges task completion

## Adding New Executors

To add a new executor:

1. Create a new file in `server/executors/`
2. Inherit from `BaseExecutor`
3. Implement required methods
4. Register in `ExecutorFactory._initialize_executors()`
5. Update `server/executors/__init__.py`

**Example:**

```python
# server/executors/custom.py
from server.executors.base import BaseExecutor

class CustomExecutor(BaseExecutor):
    def __init__(self, config):
        super().__init__("custom")
        self.config = config
    
    def is_available(self) -> bool:
        return True  # Check availability
    
    async def execute(self, agent_id, entrypoint_tag, params, **kwargs):
        # Custom execution logic
        return result
```

## Benefits of Modular Design

1. **Extensibility**: Easy to add new execution backends
2. **Testability**: Each executor can be tested independently
3. **Flexibility**: Choose executor per task
4. **Maintainability**: Clear separation of concerns
5. **Scalability**: Can add executors for different platforms

