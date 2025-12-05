"""
Consumer script for RunAgent Pulse
Polls for tasks and executes callbacks when tasks are due
"""
import sys
import os
import time
import datetime

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from sdk.runagent_pulse.client import PulseClient
except ImportError:
    print("Error: Could not import PulseClient.")
    print("Make sure you're running from the project root or SDK is installed.")
    sys.exit(1)


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    print(f"🔌 Connecting to server at {server_url}...")
    
    # Create client with unique worker ID
    worker_id = f"manual_consumer_{int(time.time())}"
    client = PulseClient(server_url=server_url)
    client.worker_id = worker_id
    
    print(f"👷 Worker ID: {worker_id}\n")
    
    # Register callback for task type
    schedule_type = "test_task_v2"
    
    @client.on_trigger(schedule_type)
    def handle_test_task(
        message: str,
        timestamp: float,
        task_id: str,
        scheduled_for: str
    ):
        """Handle incoming task execution"""
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"[{now}] ✅ Received Task")
        print(f"{'='*60}")
        print(f"   Task ID:     {task_id}")
        print(f"   Scheduled:   {scheduled_for}")
        print(f"   Message:     {message}")
        print(f"   Origin Time: {datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}")
        print(f"\n   ⏳ Processing... (simulating 2s work)")
        
        time.sleep(2)
        
        print(f"   ✅ Done!")
        print(f"{'='*60}\n")
    
    # Get registered schedule types
    registered_types = list(client.callbacks.keys())
    
    print(f"📋 Registered schedule types: {registered_types}")
    print(f"🔄 Starting polling (interval: 5 seconds)...")
    print(f"⏹️  Press Ctrl+C to stop\n")
    
    # Start polling - automatically uses registered trigger types
    client.start_polling(poll_interval=5)
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopping consumer...")
        client.stop_polling()
        print(f"👋 Goodbye!\n")


if __name__ == "__main__":
    main()
