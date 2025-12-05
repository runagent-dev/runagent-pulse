import sys
import os
import time

from runagent_pulse.client import PulseClient


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"Connecting to server at {server_url}...")
    
    client = PulseClient(server_url=server_url)

    task_name = "test_task_v2"
    print("\nScheduling recurring task: 'test_task'")
    print("  - Interval: 1 minute")
    print("  - Times: 5")
    
    try:
        task = client.schedule(
            schedule_type=task_name,
            when="now", # Start now
            payload={"message": "Hello from producer!", "timestamp": time.time()},
            repeat={"interval": "1m", "times": 5}
        )
        
        # Get task details for better output
        try:
            task_details = task.get_details()
            task_id = task.task_id
            
            print(f"\n✅ Success! Task scheduled:")
            print(f"   Task ID: {task_id}")
            print(f"   Type: {task_name}")
            print(f"   Next execution: {task_details.get('next_execution_iso', task_details.get('next_execution', 'N/A'))}")
            print(f"   Status: {task_details.get('status', 'N/A')}")
            print(f"   Will execute 5 times, every 1 minute")
            print(f"\n💡 Look for Task ID '{task_id}' in the consumer output")
            print(f"📊 Dashboard: http://localhost:8000/dashboard")
        except Exception as e:
            # Fallback if get_details fails
            task_id = task.task_id
            print(f"\n✅ Success! Task scheduled:")
            print(f"   Task ID: {task_id}")
            print(f"   Type: {task_name}")
            print(f"   Will execute 5 times, every 1 minute")
            print(f"\n💡 Look for Task ID '{task_id}' in the consumer output")
            print(f"   (Note: Could not fetch full details: {e})")
        
    except Exception as e:
        print(f"❌ Error scheduling task: {e}")

if __name__ == "__main__":
    main()
