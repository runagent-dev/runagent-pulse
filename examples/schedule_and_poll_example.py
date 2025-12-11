"""
Example: Schedule agent and poll for result (no webhook)

This example demonstrates how to schedule an agent execution and poll for results
instead of using a webhook callback.
"""
from runagent_pulse import PulseClient
import time

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule without callback
task = pulse.schedule_agent(
    agent_id="c778c025-4c9f-4466-886e-14845efe664b",
    entrypoint_tag="agno_print_response",
    when="in 1 minute",
    params={
        "prompt": "Hello!",
        "user": "test",
        "new_session": True
    }
)

print(f"Scheduled: {task.task_id}")
print("Polling for result...")

# Poll for result
while True:
    result = pulse.get_task_result(task.task_id)
    
    if result["status"] == "completed":
        print(f"✅ Result: {result['result']}")
        break
    elif result["status"] == "failed":
        print(f"❌ Failed: {result.get('error')}")
        break
    else:
        print(f"⏳ Status: {result['status']}")
        time.sleep(5)

