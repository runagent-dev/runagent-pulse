import sys
import os
import time
import datetime

# Add root to path so we can import sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from sdk.runagent_pulse.client import PulseClient
except ImportError:
    print("Error: Could not import PulseClient.")
    sys.exit(1)

def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"Connecting to server at {server_url}...")
    
    # Use a unique worker ID for this consumer
    worker_id = f"manual_consumer_{int(time.time())}"
    client = PulseClient(server_url=server_url)
    # Manually set worker_id if the client allows (it generates one by default)
    client.worker_id = worker_id
    print(f"Worker ID: {worker_id}")

    @client.on_trigger("test_task")
    def handle_test_task(message: str, timestamp: float, task_id: str, scheduled_for: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] [CONSUMER] Received task {task_id}")
        print(f"  - Scheduled for: {scheduled_for}")
        print(f"  - Message: {message}")
        print(f"  - Origin Time: {datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}")
        print("  - Processing... (simulating 2s work)")
        time.sleep(2)
        print("  - Done!")

    print("\nStarting consumer... Waiting for 'test_task'...")
    print("Press Ctrl+C to stop.")
    
    client.start_polling(poll_interval=5)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping consumer...")
        client.stop_polling()

if __name__ == "__main__":
    main()
