"""
Example: Schedule an agent execution with callback

This mirrors the recurring local example from schedule_agent_example.py.
"""
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# Schedule recurring agent execution - runs every 2 minutes (2 times)
# Pass explicit host/port so RunAgentClient(local=True) can reach your served agent
recurring_task = pulse.schedule_agent(
    agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
    entrypoint_tag="agno_print_response",
    when="in 1 minute",  # Start soon
    params={
        "prompt": "what is AI in one line?"
    },
    executor_type="local",
    agent_host="20.84.81.110",
    agent_port=8455,
    repeat={"interval": "2m", "times": 2},
    callback_url="http://webhook-handler:3001/results"
)

print(f"✅ Scheduled (Recurring every 2m)! Task ID: {recurring_task.task_id}")
print(f"📁 Result file: ./webhook-results/{recurring_task.task_id}.json")

