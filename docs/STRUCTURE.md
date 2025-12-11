# RunAgent Pulse Codebase Structure

## Overview

The codebase is organized into clear, modular sections:

```
runagent-pulse/
├── server/              # Server application
│   ├── api/             # HTTP API endpoints
│   ├── executors/       # Agent execution backends (modular)
│   ├── mcp/             # MCP (Model Context Protocol) server
│   ├── tools/           # Tool catalog and context management
│   ├── workers/         # Background workers
│   │   ├── base.py      # Base worker class
│   │   ├── expiration.py # Expiration worker
│   │   ├── webhook.py   # Webhook worker
│   │   └── agent_executor_worker.py # Agent executor worker
│   ├── database.py     # Database layer
│   ├── scheduler.py    # Task scheduling
│   ├── services.py      # Business logic (TaskService)
│   ├── dependencies.py # FastAPI dependencies
│   ├── settings.py     # Configuration
│   ├── webhook_executor.py # Webhook execution utility
│   └── main.py         # Application entry point
├── sdk/                 # Python SDK
│   └── runagent_pulse/
│       ├── client.py    # PulseClient
│       ├── tools/       # Framework-specific tools
│       └── common/      # Common utilities
├── webhook-handler/     # Webhook result handler service
├── examples/            # Example scripts
└── docs/               # Documentation
```

## Server Structure

### `/server/api/` - HTTP API Endpoints

REST API routes:
- `tasks.py` - Task management endpoints
- `tools.py` - Tool endpoints (auto-generated from catalog)
- `meta.py` - Metadata and capabilities
- `health.py` - Health checks
- `metrics.py` - Metrics
- `dashboard.py` - Dashboard

### `/server/executors/` - Agent Executors

Modular execution backends:
- `base.py` - Base executor interface
- `serverless.py` - RunAgent Serverless executor
- `local.py` - Local agent executor
- `factory.py` - Executor factory

### `/server/mcp/` - MCP Server

Model Context Protocol server:
- `server.py` - MCP server implementation
- `__init__.py` - Exports `create_mcp_server`

### `/server/tools/` - Tool Management

Tool catalog and context:
- `catalog.py` - Tool definitions and catalog
- `context.py` - Tool context builder
- `__init__.py` - Public API exports

### `/server/workers/` - Background Workers

All background workers are now in this directory:
- `base.py` - Base worker class
- `expiration.py` - ExpirationWorker (expires unclaimed tasks)
- `webhook.py` - WebhookWorker (processes webhook tasks)
- `agent_executor_worker.py` - AgentExecutorWorker (executes agents)

### Core Server Files

- `database.py` - Database layer (SQLite with WAL mode)
- `scheduler.py` - Task scheduling engine
- `services.py` - TaskService (business logic layer)
- `dependencies.py` - FastAPI dependency helpers
- `settings.py` - Configuration management
- `webhook_executor.py` - Webhook execution utility
- `main.py` - FastAPI application entry point

## SDK Structure

### `/sdk/runagent_pulse/` - Python SDK

- `client.py` - `PulseClient` main class
- `tools/` - Framework-specific tool adapters
- `common/` - Shared utilities and contracts
- `tool_registry.py` - Tool registry
- `tool_catalog.py` - SDK-side tool catalog
- `time.py` - TimeParser (shared with server)

## Key Design Principles

1. **Modularity**: Each major feature is in its own folder
2. **Separation of Concerns**: API, business logic, and infrastructure are separated
3. **Extensibility**: Easy to add new executors, tools, or workers
4. **Clear Imports**: Organized imports with `__init__.py` files
5. **No Redundancy**: Removed duplicate files (workers.py, time_parser.py shim)

## Import Patterns

### Server-side

```python
# Workers
from server.workers import ExpirationWorker, WebhookWorker, AgentExecutorWorker

# Tools
from server.tools import list_tools, build_tool_context

# MCP
from server.mcp import create_mcp_server

# Executors
from server.executors import ExecutorFactory, ServerlessExecutor

# Core
from server.scheduler import Scheduler
from server.services import TaskService
from server.database import Database
from runagent_pulse.time import TimeParser  # Direct from SDK
```

### SDK-side

```python
# Client
from runagent_pulse import PulseClient

# Tools
from runagent_pulse.tools import crewai, langgraph
```

## File Organization Decisions

### Consolidated Workers

- **Before**: `workers.py` at root + `workers/` directory
- **After**: All workers in `workers/` directory
- **Reason**: Consistency and better organization

### Removed Shim Files

- **Removed**: `time_parser.py` (3-line shim)
- **Reason**: Direct import from SDK is cleaner: `from runagent_pulse.time import TimeParser`

### Core Files Kept

- `scheduler.py` - Core scheduling logic (510 lines)
- `services.py` - Service layer abstraction
- `dependencies.py` - FastAPI dependency pattern
- `database.py` - Database layer
- `settings.py` - Configuration

These are core components that belong at the root level.

## Adding New Components

### Adding a New Worker

1. Create `server/workers/my_worker.py`
2. Inherit from `BaseWorker`
3. Register in `server/workers/__init__.py`
4. Start in `server/main.py` lifespan

### Adding a New Executor

1. Create `server/executors/my_executor.py`
2. Inherit from `BaseExecutor`
3. Register in `ExecutorFactory._initialize_executors()`
4. Update `server/executors/__init__.py`

### Adding a New Tool

1. Add tool definition to SDK `runagent_pulse/common/tooling.py`
2. Add implementation to `server/tools/catalog.py`
3. Tool automatically exposed via API and MCP
