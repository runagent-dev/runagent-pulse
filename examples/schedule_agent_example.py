"""
Example: Schedule an agent execution with callback

This example demonstrates how to schedule an agent execution via RunAgent Serverless
or RunAgent Local, and receive results via webhook callback.
"""
from runagent_pulse import PulseClient

# Initialize Pulse client
pulse = PulseClient(server_url="http://localhost:8000")

# # Schedule agent with RunAgent Serverless (local=False or not specified)
# task = pulse.schedule_agent(
#     agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
#     entrypoint_tag="agno_print_response",
#     when="in 30 seconds",
#     params={
#         "prompt": "write me a cat story"
#     },
#     executor_type="serverless",  # Use serverless executor (required for RunAgent Serverless agents)
#     local=False,  # Use RunAgent Serverless (default behavior)
#     # Use Docker service name (works for callbacks from Pulse container)
#     # For external access, use: http://<VM_IP>:3001/results
#     callback_url="http://webhook-handler:3001/results"
# )

# print(f"✅ Scheduled (Serverless)! Task ID: {task.task_id}")

# # Schedule agent with RunAgent Local (local=True)
# local_task = pulse.schedule_agent(
#     agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
#     entrypoint_tag="agno_print_response",
#     when="in 1 minute",
#     params={
#         "prompt": "write me a dog story"
#     },
#     executor_type="serverless",  # Still use serverless executor, but with local=True
#     local=True,  # Use RunAgent Local execution
#     callback_url="http://webhook-handler:3001/results"
# )

# print(f"✅ Scheduled (Local)! Task ID: {local_task.task_id}")

# Schedule recurring agent execution - runs every 30 seconds
recurring_task = pulse.schedule_agent(
    agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
    entrypoint_tag="agno_print_response",
    when="in 1 minute",  # Start immediately
    params={
        "prompt": "what is GPU in one line?"
    },
    executor_type="serverless",
    local=False,
    repeat={"interval": "2m", "times": 2},  # Every 30 seconds, infinite
    callback_url="http://webhook-handler:3001/results"
)

print(f"✅ Scheduled (Recurring every 30s)! Task ID: {recurring_task.task_id}")
print(f"📁 Result file: ./webhook-results/{recurring_task.task_id}.json")
# # Schedule limited recurring agent execution - runs 5 times, every 1 minute
# limited_recurring_task = pulse.schedule_agent(
#     agent_id="ae29bd73-b3d3-99c8-a98f-5d7aec7ee911",
#     entrypoint_tag="agno_print_response",
#     when="in 1 minute",
#     params={
#         "prompt": "write me a limited story"
#     },
#     executor_type="serverless",
#     local=False,
#     repeat={"interval": "1m", "times": 5},  # Every 1 minute, 5 times total
#     callback_url="http://webhook-handler:3001/results"
# )

# print(f"✅ Scheduled (Limited recurring - 5 times)! Task ID: {limited_recurring_task.task_id}")
# print(f"📊 Check logs: docker logs -f runagent-webhook-handler")
# print(f"📁 Result file: ./webhook-results/{task.task_id}.json")

