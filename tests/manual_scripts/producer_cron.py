"""
Producer script for cron-based tasks
Schedules a task to run based on cron expressions
"""
import sys
import os
import time

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from runagent_pulse.client import PulseClient


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"Connecting to server at {server_url}...")
    
    client = PulseClient(server_url=server_url)
    
    # Schedule a cron-based task
    schedule_type = "test_task_v2"
    cron_expr = "*/2 * * * *"  # Every 2 minutes
    
    print(f"\n⏰ Scheduling cron task:")
    print(f"   Type: {schedule_type}")
    print(f"   Cron: {cron_expr} (every 2 minutes)")
    
    try:
        task = client.schedule(
            schedule_type=schedule_type,
            when={
                "type": "cron",
                "cron": cron_expr
            },
            payload={
                "message": "Hello from cron task!",
                "timestamp": time.time(),
                "task_type": "cron"
            }
        )
        
        # Get task details
        try:
            task_details = task.get_details()
            task_id = task.task_id
            
            print(f"\n✅ Task scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Next execution: {task_details.get('next_execution_iso', task_details.get('next_execution', 'N/A'))}")
            print(f"   Status: {task_details.get('status', 'N/A')}")
            print(f"   Cron expression: {cron_expr}")
            print(f"\n💡 Look for Task ID '{task_id}' in the consumer output")
            print(f"📊 Dashboard: http://localhost:8000/dashboard")
        except Exception as e:
            task_id = task.task_id
            print(f"\n✅ Task scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Cron expression: {cron_expr}")
            print(f"   (Note: Could not fetch full details: {e})")
        
    except Exception as e:
        print(f"❌ Error scheduling task: {e}")


if __name__ == "__main__":
    main()

