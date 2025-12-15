"""
PaperFlow Scheduling - Copy & Paste Example

SETUP:
1. Install: pip install runagent-pulse
2. Edit AGENT_ID and TOPICS below
3. Run: python schedule_paperflow.py daily
"""

from runagent_pulse import PulseClient

# ============================================================================
# CONFIGURATION - EDIT THESE
# ============================================================================

PULSE_SERVER_URL = "http://localhost:8000"              # Your Pulse server
AGENT_ID = "62f7a781-71bb-4d62-a68f-34dc4f2bfd0b"      # Your deployed agent ID

TOPICS = [
"fine-tuning vision language models"
]

# ============================================================================
# FUNCTION 1: DAILY SCHEDULE
# ============================================================================

def schedule_daily():
    """Run once per day at 9:00 AM"""
    
    pulse = PulseClient(server_url=PULSE_SERVER_URL)
    
    print("=" * 70)
    print("Scheduling PaperFlow - Daily Mode")
    print("=" * 70)
    
    task = pulse.schedule_agent(
        agent_id=AGENT_ID,
        entrypoint_tag="check_papers_async",
        when="daily at 9am",
        params={
            "topics": TOPICS,
            "max_results": 20,
            "days_back": 7,
            "verbose": True
        },
        executor_type="serverless",
        user_id="paperflow_daily",
        persistent_memory=True
    )
    
    print(f"\n✅ Scheduled daily at 9:00 AM")
    print(f"📋 Task ID: {task.task_id}")
    print(f"📧 Email: Enabled")
    print(f"💾 Cache: Enabled")
    
    return task


# ============================================================================
# FUNCTION 2: RECURRING SCHEDULE
# ============================================================================

def schedule_recurring(interval="10m", times=1):
    """Run at regular intervals (e.g., every 6 hours)"""
    
    pulse = PulseClient(server_url=PULSE_SERVER_URL)
    
    print("=" * 70)
    print("Scheduling PaperFlow - Recurring Mode")
    print("=" * 70)
    
    task = pulse.schedule_agent(
        agent_id=AGENT_ID,
        entrypoint_tag="check_papers_async",
        when="in 3 minute",  # Start soon
        params={
            "topics": TOPICS,
            "max_results": 20,
            "days_back": 100,
            "verbose": True
        },
        executor_type="serverless",
        user_id="paperflow_recurring",
        persistent_memory=True,
        repeat={
            "interval": interval,
            "times": times  # None = infinite
        }
    )
    
    times_str = f"{times} times" if times else "infinite"
    print(f"\n✅ Scheduled every {interval} ({times_str})")
    print(f"📋 Task ID: {task.task_id}")
    print(f"📧 Email: Enabled")
    print(f"💾 Cache: Enabled")
    
    return task


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("\nPaperFlow Scheduler")
    print("=" * 70)
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "daily":
            schedule_daily()
        
        elif mode == "recurring":
            interval = sys.argv[2] if len(sys.argv) > 2 else "6h"
            times = int(sys.argv[3]) if len(sys.argv) > 3 else None
            schedule_recurring(interval=interval, times=times)
        
        else:
            print("\nUsage:")
            print("  python schedule_paperflow.py daily")
            print("  python schedule_paperflow.py recurring 6h")
            print("  python schedule_paperflow.py recurring 2h 5")
    else:
        print("\nUsage:")
        print("  python schedule_paperflow.py daily              # Once daily at 9am")
        print("  python schedule_paperflow.py recurring 6h       # Every 6 hours")
        print("  python schedule_paperflow.py recurring 2h 5     # Every 2 hours, 5 times")
        print("\nIntervals: 30m, 1h, 2h, 6h, 12h, 1d")


# ============================================================================
# EXAMPLES - Use in Python script or Jupyter notebook
# ============================================================================

"""
# Example 1: Schedule daily
from runagent_pulse import PulseClient

pulse = PulseClient(server_url="http://localhost:8000")

task = pulse.schedule_agent(
    agent_id="62f7a781-71bb-4d62-a68f-24dc4f2bfd0b",
    entrypoint_tag="check_papers",
    when="daily at 9am",
    params={
        "topics": ["LLM finetuning"],
        "max_results": 20,
        "days_back": 7
    },
    executor_type="serverless",
    user_id="paperflow",
    persistent_memory=True
)

print(f"Scheduled: {task.task_id}")


# Example 2: Recurring every 6 hours
task = pulse.schedule_agent(
    agent_id="62f7a781-71bb-4d62-a68f-24dc4f2bfd0b",
    entrypoint_tag="check_papers",
    when="in 1 minute",
    params={
        "topics": ["LLM finetuning"],
        "max_results": 20,
        "days_back": 7
    },
    executor_type="serverless",
    user_id="paperflow",
    persistent_memory=True,
    repeat={"interval": "6h", "times": None}  # infinite
)

print(f"Scheduled: {task.task_id}")


# Example 3: Recurring 5 times only
task = pulse.schedule_agent(
    agent_id="62f7a781-71bb-4d62-a68f-24dc4f2bfd0b",
    entrypoint_tag="check_papers",
    when="in 1 minute",
    params={
        "topics": ["LLM finetuning"],
        "max_results": 20,
        "days_back": 7
    },
    executor_type="serverless",
    user_id="paperflow",
    persistent_memory=True,
    repeat={"interval": "2h", "times": 5}  # 5 times
)

print(f"Scheduled: {task.task_id}")
"""