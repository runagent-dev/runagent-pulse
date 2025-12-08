"""MCP server auto-generated from tool catalog and registry."""
from fastmcp import FastMCP
from runagent_pulse.tool_registry import ToolRegistry, create_registry
from server.tool_catalog import list_tools_for
from server.tool_context import build_tool_context
import json
import inspect


def _upsert_tool(registry: ToolRegistry, name: str, description: str, param_model, implementation):
    """Register or replace a tool definition."""
    registry.register_tool(
        name=name,
        description=description,
        param_model=param_model,
        implementation=implementation,
    )


def create_mcp_server(db, scheduler, task_service, registry: ToolRegistry | None = None, settings=None):
    """Create MCP server with catalog-selected tools and return its ASGI app."""
    registry = registry or create_registry()
    mcp = FastMCP("runagent-pulse")

    # Register tools from catalog with real implementations
    for tool_def in list_tools_for("mcp"):
        async def impl(params, tool_def=tool_def):
            ctx = build_tool_context(
                task_service=task_service,
                db=db,
                scheduler=scheduler,
                settings=settings,
            )
            return await tool_def.impl(ctx, params)

        _upsert_tool(
            registry,
            tool_def.name,
            tool_def.description,
            tool_def.request_model,
            impl,
        )

    # Dynamically create MCP tools from registry using explicit signatures (no *args/**kwargs)
    for tool_def in registry.list_tools():

        def create_tool_function(name, param_model):
            async def tool_function(payload: dict) -> str:
                try:
                    params = param_model(**payload)
                    impl = registry.tools[name].implementation
                    result = impl(params)
                    if inspect.iscoroutine(result):
                        result = await result

                    # Standardize response format
                    if isinstance(result, dict):
                        if "error" in result:
                            return json.dumps({
                                "success": False,
                                "error": result["error"]
                            })
                        else:
                            return json.dumps({
                                "success": True,
                                "data": result
                            })
                    else:
                        return json.dumps({
                                "success": True,
                                "result": str(result)
                            })

                except Exception as e:
                    return json.dumps({
                        "success": False,
                        "error": str(e)
                    })

            tool_function.__name__ = name
            tool_function.__doc__ = tool_def.description
            return tool_function

        tool_func = create_tool_function(tool_def.name, tool_def.param_model)

        # Register with MCP - FastMCP will infer schema from explicit signature
        mcp.tool(
            name=tool_def.name,
            description=tool_def.description
        )(tool_func)

    # Build ASGI app for mounting; use path="/" so mounting prefix controls URL
    mcp_app = mcp.http_app(path="/")
    return mcp_app
