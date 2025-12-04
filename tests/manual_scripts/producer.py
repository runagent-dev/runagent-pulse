import sys
import os
import time

# Add root to path so we can import sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from sdk.runagent_pulse.client import PulseClient
except ImportError:
    print("Error: Could not import PulseClient. Make sure you are running this script from the project root or have installed the SDK.")
    print("Try running: export PYTHONPATH=$PYTHONPATH:$(pwd)")
    sys.exit(1)

def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"Connecting to server at {server_url}...")
    
    client = PulseClient(server_url=server_url)

    print("\nScheduling recurring task: 'test_task'")
    print("  - Interval: 1 minute")
    print("  - Times: 5")
    
    try:
        # Note: The SDK's schedule method helper might not expose 'times' directly in the 'repeat' dict if it constructs it manually.
        # Let's check client.py schedule method signature.
        # It takes repeat: Optional[dict]. So we can pass the raw dict.
        
        task_id = client.schedule(
            schedule_type="test_task",
            when="now", # Start now
            payload={"message": "Hello from producer!", "timestamp": time.time()},
            repeat={"interval": "1m", "times": 5}
        )
        print(f"Success! Task scheduled with ID: {task_id}")
        print("Check the dashboard at http://localhost:8000/dashboard to see the tasks.")
        
    except Exception as e:
        print(f"Error scheduling task: {e}")

if __name__ == "__main__":
    main()
