"""
Producer script for webhook tasks
Schedules a one-time webhook task with optional timeout/retries
"""
import os
import sys
import time

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from runagent_pulse.client import PulseClient


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    webhook_url = os.getenv("PULSE_WEBHOOK_URL", "https://webhook.site/7171d2dc-d675-42cd-aea7-433cfb4cff77")
    webhook_timeout = int(os.getenv("PULSE_WEBHOOK_TIMEOUT", "30"))
    webhook_retries = int(os.getenv("PULSE_WEBHOOK_RETRIES", "3"))

    print(f"Connecting to server at {server_url}...")
    print(f"Using webhook URL: {webhook_url}")
    print(f"Webhook timeout: {webhook_timeout}s, retries: {webhook_retries}")

    client = PulseClient(server_url=server_url)

    schedule_type = "webhook_task"
    when = "in 30 seconds"

    print("\n🚀 Scheduling webhook task:")
    print(f"   Type: {schedule_type}")
    print(f"   When: {when}")
    print(f"   Webhook: {webhook_url}")

    try:
        task = client.schedule(
            schedule_type=schedule_type,
            when=when,
            payload={
                "message": "Hello from webhook producer!",
                "timestamp": time.time(),
            },
            webhook_url=webhook_url,
            webhook_timeout=webhook_timeout,
            webhook_retries=webhook_retries,
        )

        # Get task details
        try:
            task_details = task.get_details()
            task_id = task.task_id

            print("\n✅ Task scheduled successfully!")
            print(f"   Task ID:        {task_id}")
            print(f"   Next execution: {task_details.get('next_execution_iso', task_details.get('next_execution', 'N/A'))}")
            print(f"   Status:         {task_details.get('status', 'N/A')}")
            print(f"\nℹ️  Webhook tasks are executed by server-side worker, not via polling.")
        except Exception as e:
            task_id = task.task_id
            print("\n✅ Task scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   (Note: Could not fetch full details: {e})")

    except Exception as e:
        print(f"❌ Error scheduling task: {e}")


if __name__ == "__main__":
    main()

