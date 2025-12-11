"""
Example: Schedule HTTP requests with RunAgent Pulse (Standalone Mode)

This example demonstrates how to use RunAgent Pulse as a standalone scheduling service
to schedule HTTP requests to any endpoint. This is useful for integrating with:
- LangGraph agents
- Agno agents
- Custom agentic frameworks
- MCP servers
- Any HTTP-based service

The developer runs their own server/endpoint, and Pulse hits that endpoint at scheduled times.
"""
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule morning routine
morning_task = pulse.schedule_http(
    url="http://localhost:5000/agents/morning-routine",
    method="POST",
    when="daily at 9am",
    body={"user": "sawradip"},
    headers={"Authorization": "Bearer my-secret-token"}
)

print(f"✅ Scheduled morning routine! Task ID: {morning_task.task_id}")

# Schedule data sync every hour
sync_task = pulse.schedule_http(
    url="http://localhost:5000/agents/data-sync",
    method="POST",
    when="hourly",
    body={"source": "database"}
)

print(f"✅ Scheduled data sync! Task ID: {sync_task.task_id}")

# Schedule daily report
report_task = pulse.schedule_http(
    url="http://localhost:5000/agents/daily-report",
    method="POST",
    when="daily at 6pm",
    body={"email": "sawradip@example.com"}
)

print(f"✅ Scheduled daily report! Task ID: {report_task.task_id}")

# Schedule a one-time task in 30 seconds
immediate_task = pulse.schedule_http(
    url="http://localhost:5000/agents/test",
    method="POST",
    when="in 30 seconds",
    body={"test": "data"}
)

print(f"✅ Scheduled immediate task! Task ID: {immediate_task.task_id}")
print(f"📊 Check dashboard: http://localhost:8000/dashboard")
print(f"📁 View task details: pulse.get_task('{immediate_task.task_id}')")

