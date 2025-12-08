"""
CrewAI tools for RunAgent Pulse using the shared catalog.
"""
from typing import List, ClassVar, Type
import json

try:
    from crewai.tools import BaseTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object

from runagent_pulse.tool_catalog import TOOL_META
from runagent_pulse.client import PulseClient as BasePulseClient


def _create_crewai_tool(meta, client):
    if not CREWAI_AVAILABLE:
        raise ImportError("CrewAI is not installed")

    class GeneratedTool(BaseTool):
        name: str = meta.name
        description: str = meta.description
        args_schema: ClassVar[Type] = meta.request_model

        def _run(self, **kwargs) -> str:
            try:
                result = client.call_tool(meta.name, **kwargs)
                if isinstance(result, dict) and "error" in result:
                    return f"❌ {result['error']}"
                return json.dumps(result)
            except Exception as exc:  # pragma: no cover - network errors, etc.
                return f"❌ Error calling tool: {exc}"

    GeneratedTool.__name__ = f"{meta.name}_CrewAITool"
    return GeneratedTool


class PulseClient(BasePulseClient):
    """
    Convenience wrapper that exposes framework-specific tools as methods.
    Scripts can do:
        from runagent_pulse.tools.crewai import PulseClient
        client = PulseClient(server_url)
        tool = client.get_tool("schedule_task")
    """

    def list_available_tools(self) -> List[str]:
        return [meta.name for meta in TOOL_META if "crewai" in meta.expose_frameworks]

    def get_tool(self, name: str):
        meta = next((m for m in TOOL_META if m.name == name and "crewai" in m.expose_frameworks), None)
        if not meta:
            raise ValueError(f"Tool '{name}' not available for CrewAI")
        ToolCls = _create_crewai_tool(meta, self)
        return ToolCls()

    # Backward-compatible helpers
    def ScheduleTaskTool(self):
        return self.get_tool("schedule_task")

    def ListTasksTool(self):
        return self.get_tool("list_tasks")

    def CancelTaskTool(self):
        return self.get_tool("cancel_task")

    def GetTaskDetailsTool(self):
        return self.get_tool("get_task_details")
