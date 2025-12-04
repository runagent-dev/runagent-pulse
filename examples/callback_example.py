"""
Callback-based execution example
"""
from runagent_pulse import PulseClient
import time

pc = PulseClient(server_url="http://localhost:8000")

# Register callback for email sending
@pc.on_trigger("send_mail")
def handle_send_mail(to: str, body: str, task_id: str, scheduled_for: str):
    """Handle email sending"""
    print(f"[{scheduled_for}] Sending email to {to}")
    print(f"Body: {body}")
    print(f"Task ID: {task_id}")
    
    # Simulate email sending
    time.sleep(0.5)
    
    return {"status": "sent", "recipient": to}

# Register callback for food ordering
@pc.on_trigger("order_food")
def handle_order_food(name: str, count: int, task_id: str):
    """Handle food ordering"""
    print(f"Ordering {count}x {name}")
    return {"status": "ordered"}

# Schedule some tasks
print("Scheduling tasks...")

pc.schedule(
    "send_mail",
    "in 10 seconds",
    {"to": "alice@example.com", "body": "Meeting reminder"}
)

pc.schedule(
    "order_food",
    "in 15 seconds",
    {"name": "Pizza", "count": 2}
)

# Start polling (blocking)
print("Starting polling...")
pc.start_polling(
    poll_interval=2,
    schedule_types=["send_mail", "order_food"]
)

