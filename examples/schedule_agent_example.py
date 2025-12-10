"""
Example: Schedule an agent execution with callback

This example demonstrates how to schedule an agent execution via RunAgent Serverless
and receive results via webhook callback.
"""
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule agent
task = pulse.schedule_agent(
    agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
    entrypoint_tag="agno_print_response",
    when="in 30 seconds",
    params={
        "prompt": "write me a cat story"
    },
    executor_type="serverless",  # Use serverless executor (required for RunAgent Serverless agents)
    # Use Docker service name (works for callbacks from Pulse container)
    # For external access, use: http://<VM_IP>:3001/results
    callback_url="http://webhook-handler:3001/results"
)

print(f"✅ Scheduled! Task ID: {task.task_id}")
print(f"📊 Check logs: docker logs -f runagent-webhook-handler")
print(f"📁 Result file: ./webhook-results/{task.task_id}.json")

