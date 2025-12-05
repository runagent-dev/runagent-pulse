"""
Producer script for one-time tasks
Schedules a task to run once at a specific time
"""
import sys
import os
import time
from datetime import datetime, timedelta

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from runagent_pulse.client import PulseClient


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"Connecting to server at {server_url}...")
    
    client = PulseClient(server_url=server_url)
    
    # Schedule a one-time task
    schedule_type = "test_task_v2"
    when = "in 90 seconds"  # Natural language or ISO 8601
    
    print(f"\n📅 Scheduling one-time task:")
    print(f"   Type: {schedule_type}")
    print(f"   When: {when}")
    
    try:
        task = client.schedule(
            schedule_type=schedule_type,
            when=when,
            payload={
                "message": "This is a one-time task!",
                "timestamp": time.time(),
                "task_type": "one_time"
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
            print(f"\n💡 Look for Task ID '{task_id}' in the consumer output")
            print(f"📊 Dashboard: http://localhost:8000/dashboard")
        except Exception as e:
            task_id = task.task_id
            print(f"\n✅ Task scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   (Note: Could not fetch full details: {e})")
        
    except Exception as e:
        print(f"❌ Error scheduling task: {e}")


if __name__ == "__main__":
    main()

