"""
LangGraph tools for RunAgent Pulse using the shared catalog.
"""
from typing import List, ClassVar, Type
import json

try:
    from langchain_core.tools import BaseTool as LangChainTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    LangChainTool = object

from runagent_pulse.tool_catalog import TOOL_META
from runagent_pulse.client import PulseClient as BasePulseClient


def _create_langgraph_tool(meta, client):
    if not LANGCHAIN_AVAILABLE:
        raise ImportError("LangChain is not installed")

    class GeneratedTool(LangChainTool):
        name: str = meta.name
        description: str = meta.description
        args_schema: ClassVar[Type] = meta.request_model

        def _run(self, **kwargs) -> str:
            try:
                result = client.call_tool(meta.name, **kwargs)
                return json.dumps(result)
            except Exception as exc:  # pragma: no cover - network errors, etc.
                return json.dumps({"error": str(exc)})

    GeneratedTool.__name__ = f"{meta.name}_LangGraphTool"
    return GeneratedTool


class PulseClient(BasePulseClient):
    """
    Convenience wrapper that exposes framework-specific tools as methods.
    Scripts can do:
        from runagent_pulse.tools.langgraph import PulseClient
        client = PulseClient(server_url)
        tool = client.get_tool("schedule_task")
    """

    def list_available_tools(self) -> List[str]:
        return [meta.name for meta in TOOL_META if "langgraph" in meta.expose_frameworks]

    def get_tool(self, name: str, **kwargs) -> LangChainTool:
        meta = next((m for m in TOOL_META if m.name == name and "langgraph" in m.expose_frameworks), None)
        if not meta:
            raise ValueError(f"Tool '{name}' not available for LangGraph")
        ToolCls = _create_langgraph_tool(meta, self)
        return ToolCls(**kwargs)

    # Backward-compatible helpers
    def ScheduleTaskTool(self, **kwargs):
        return self.get_tool("schedule_task", **kwargs)

    def ListTasksTool(self, **kwargs):
        return self.get_tool("list_tasks", **kwargs)

    def CancelTaskTool(self, **kwargs):
        return self.get_tool("cancel_task", **kwargs)

    def GetTaskDetailsTool(self, **kwargs):
        return self.get_tool("get_task_details", **kwargs)
