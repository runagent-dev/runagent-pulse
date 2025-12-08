"""
Minimal FastMCP client example hitting the FastAPI-mounted MCP server.

This script:
1) Lists available MCP tools via FastMCP client
2) Invokes the schedule_task tool to schedule a one-time task in 1 minute

Requires: fastmcp (pip install fastmcp)
"""
import os
import asyncio
import json

from fastmcp import Client as FastMCPClient


async def main_async():

    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    api_key = os.getenv("PULSE_API_KEY")
    base_url = f"{server_url}/mcp"

    print(f"Target MCP server: {base_url}")

    client = FastMCPClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
    )

    # 1) List tools
    print("\n1) Listing tools via FastMCP...")
    tools = await client.list_tools()
    print(json.dumps(tools, indent=2))

    # 2) Invoke schedule_task
    print("\n2) Invoking schedule_task via FastMCP...")
    result = await client.call_tool(
        "schedule_task",
        schedule_type="demo_mcp_fastmcp",
        when="in 1 minute",
        payload={"source": "producer_mcp.py", "message": "Hello from FastMCP client"},
    )
    print(json.dumps(result, indent=2))

    print("\n✅ MCP tool call completed (check the Pulse dashboard).")
    await client.aclose()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()