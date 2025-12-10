"""
Example: Schedule a local agent execution

This example demonstrates how to schedule an agent that runs locally
(not via RunAgent Serverless).
"""
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule local agent execution
# agent_id should be a Python module name that can be imported
task = pulse.schedule_agent(
    agent_id="my_local_agent",  # Python module name
    entrypoint_tag="process",
    when="in 1 minute",
    params={
        "input": "Hello from Pulse!",
        "user": "developer"
    },
    executor_type="local",  # Use local executor
    callback_url="http://webhook-handler:3001/results"
)

print(f"✅ Scheduled local agent! Task ID: {task.task_id}")
print(f"📊 Check logs: docker logs -f runagent-pulse")
print(f"📁 Result file: ./webhook-results/{task.task_id}.json")

# Example local agent module structure:
# my_local_agent/
#   __init__.py
#   process.py  # Contains process() function
#
# Or as a single module:
# my_local_agent.py  # Contains process() function

