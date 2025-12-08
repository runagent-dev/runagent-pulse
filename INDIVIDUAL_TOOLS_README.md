# Individual Tools System

This new system provides **separate, model-driven tools** for RunAgent Pulse, giving you fine-grained control over which capabilities each agent gets.

## Key Benefits

✅ **Modular**: Import only the tools each agent needs
✅ **Model-Driven**: Schemas come from Pydantic models automatically
✅ **Consistent**: Same validation and descriptions everywhere
✅ **Simple**: Clean interfaces for each framework

## Available Tools

| Tool | Purpose | CrewAI | LangGraph | MCP |
|------|---------|--------|-----------|-----|
| `ScheduleTaskTool` | Schedule new tasks | ✅ | ✅ | ✅ |
| `ListTasksTool` | List/filter tasks | ✅ | ✅ | ✅ |
| `CancelTaskTool` | Cancel tasks | ✅ | ✅ | ✅ |
| `GetTaskDetailsTool` | Get task info + history | ✅ | ✅ | ✅ |

## Usage Examples

### CrewAI Agent (Minimal Setup)

```python
from runagent_pulse.tools import crewai
from runagent_pulse.client import PulseClient

# Connect to server
client = PulseClient("http://localhost:8000", api_key="your-key")

# One import gets all CrewAI tools - pick what you need
schedule_tool = crewai.ScheduleTaskTool(client)

# Use in CrewAI agent
agent = CrewAgent(
    tools=[schedule_tool],  # Clean, focused toolset
    task="Schedule a daily report email every weekday at 9am"
)
```

### CrewAI Agent (Full Featured)

```python
from runagent_pulse.tools import crewai
from runagent_pulse.client import PulseClient

client = PulseClient("http://localhost:8000", api_key="your-key")

# All tools available through single import
agent = CrewAgent(
    tools=[
        crewai.ScheduleTaskTool(client),
        crewai.ListTasksTool(client),
        crewai.CancelTaskTool(client)
    ],
    task="Monitor tasks and schedule follow-ups as needed"
)
```

### LangGraph Agent (Complete Toolkit)

```python
from runagent_pulse.tools import langgraph
from runagent_pulse.client import PulseClient

client = PulseClient("http://localhost:8000", api_key="your-key")

# All LangGraph tools available through single import
tools = [
    langgraph.ScheduleTaskTool(client),    # For scheduling
    langgraph.ListTasksTool(client),       # For monitoring
    langgraph.CancelTaskTool(client),      # For cleanup
    langgraph.GetTaskDetailsTool(client)   # For inspection
]

# Build LangGraph agent with complete toolset
workflow = create_workflow(tools)
agent = workflow.compile()
```

### MCP Integration

The MCP server at `/mcp` automatically exposes all registered tools with proper schemas:

```bash
# MCP clients get all tools automatically
curl http://localhost:8000/mcp/tools/list
```

## Tool Parameters

All tool parameters are defined in Pydantic models in `runagent_pulse.models`, ensuring:

- **Automatic validation** of all inputs
- **Rich descriptions** for each parameter
- **Type safety** across all frameworks
- **Consistent schemas** in MCP

### Schedule Task Parameters

```python
schedule_type: str          # "send_email", "webhook_call", etc.
when: str                   # "tomorrow at 2pm", "0 9 * * 1-5", etc.
payload: Optional[Dict]     # Task-specific data
repeat: Optional[Dict]      # Recurring configuration
metadata: Optional[Dict]    # Organization tags
webhook_url: Optional[str]  # Completion callback URL
webhook_timeout: Optional[int]  # Callback timeout
webhook_retries: Optional[int]  # Retry attempts
```

### List Tasks Parameters

```python
status: Optional[str]       # Filter by status
schedule_type: Optional[str]  # Filter by type
limit: int                  # Max results (default: 10)
offset: int                 # Pagination offset (default: 0)
```

## Architecture

```
runagent_pulse.models          # Pydantic parameter models
    ↓
runagent_pulse.tool_registry   # Auto-generates schemas + shared implementations
    ↓
Framework Namespaces           # One per framework (crewai, langgraph)
    ↓
Individual Tool Classes        # All tools in each framework namespace
    ↓
CrewAI/LangGraph/MCP           # Clean, focused interfaces
```

**DRY Principle**: One implementation in the registry, reused across all frameworks!

## Migration from Old System

**Old way** (monolithic):
```python
# One tool does everything - overwhelming for agents
from runagent_pulse.tools.crewai import PulseSchedulerTool
tool = PulseSchedulerTool(client)  # 20+ parameters, complex logic
```

**New way** (framework-specific):
```python
# One import per framework - clean namespace management
from runagent_pulse.tools import crewai

tools = [
    crewai.ScheduleTaskTool(client),    # Just scheduling
    # No listing = cleaner agent behavior
]
```

## Best Practices

1. **Be Specific**: Only give agents the tools they actually need
2. **Start Minimal**: Add tools incrementally as agents require them
3. **Test Interactions**: Complex tool combinations can confuse agents
4. **Use Descriptions**: Pydantic field descriptions help agents understand parameters

## Framework-Specific Notes

### CrewAI
- Tools return formatted strings optimized for human reading
- Automatic error handling with user-friendly messages
- Integrates seamlessly with CrewAI's task system

### LangGraph
- Tools return structured JSON data
- Designed for programmatic processing in workflows
- Compatible with LangChain tool calling patterns

### MCP
- All tools available at `/mcp` endpoint
- Automatic schema generation from Pydantic models
- Compatible with any MCP client (Claude Desktop, etc.)

This system gives you maximum flexibility while maintaining consistency and simplicity across all your AI agent integrations! 🚀
