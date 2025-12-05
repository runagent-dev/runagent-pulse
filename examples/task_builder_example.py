"""
Task Builder example
"""
from runagent_pulse import PulseClient, TaskBuilder

pc = PulseClient(server_url="http://localhost:8000")

# Using Task Builder for fluent task creation
task = (
    TaskBuilder(pc)
    .type("send_mail")
    .in_("tomorrow at 2pm")
    .with_payload(
        to="user@example.com",
        body="Daily report",
        subject="Report"
    )
    .repeat(times=5, every="1 day")
    .tag("important", "report")
    .with_metadata(created_by="admin", priority="high")
    .build()
)

print(f"Created task: {task.id}")

# Get execution history after some time
# history = task.get_history()
# for execution in history:
#     print(f"{execution['executed_at_iso']}: {execution['status']}")


