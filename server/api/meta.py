"""Capabilities and metadata endpoints."""
from fastapi import APIRouter, Depends

from server.dependencies import verify_api_key
from server.tool_catalog import list_tools

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/tools", dependencies=[Depends(verify_api_key)])
async def list_tool_capabilities():
    """Return catalog metadata and schemas for available tools."""
    tools = []
    for tool in list_tools():
        request_schema = tool.request_model.model_json_schema() if tool.request_model else None
        response_schema = tool.response_model.model_json_schema() if tool.response_model else None
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "expose_http": tool.expose_http,
                "expose_mcp": tool.expose_mcp,
                "expose_frameworks": list(tool.expose_frameworks),
                "tags": list(tool.tags),
                "request_schema": request_schema,
                "response_schema": response_schema,
            }
        )
    return {"tools": tools, "count": len(tools)}

