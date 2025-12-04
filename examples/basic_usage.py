"""
Basic usage example for RunAgent Pulse
"""
from runagent_pulse import PulseClient

# Initialize client
pc = PulseClient(server_url="http://localhost:8000")

# Schedule a simple task
task = pc.schedule(
    schedule_type="send_mail",
    when="in 5 minutes",
    payload={
        "to": "user@example.com",
        "body": "Hello from RunAgent Pulse!"
    }
)

print(f"Scheduled task: {task.id}")

# Get task details
details = task.get_details()
print(f"Next execution: {details['next_execution_iso']}")

# Cancel the task
# task.cancel()

