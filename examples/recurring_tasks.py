"""
Recurring tasks example
"""
from runagent_pulse import PulseClient

pc = PulseClient(server_url="http://localhost:8000")

# Schedule recurring task with cron
daily_task = pc.schedule(
    "daily_report",
    {"type": "cron", "cron": "0 9 * * *"},  # Daily at 9am
    {"report_type": "summary"}
)

print(f"Daily report task: {daily_task.id}")

# Schedule recurring task with interval
hourly_task = pc.schedule(
    "health_check",
    {
        "type": "recurring",
        "delay": "1m",
        "repeat": {"interval": "1h", "times": None}  # Infinite
    },
    {"service": "api"}
)

print(f"Hourly health check task: {hourly_task.id}")

# Schedule task with limited repetitions
limited_task = pc.schedule(
    "send_reminder",
    {
        "type": "recurring",
        "delay": "5m",
        "repeat": {"interval": "30m", "times": 3}  # 3 times
    },
    {"message": "Don't forget!"}
)

print(f"Limited reminder task: {limited_task.id}")


