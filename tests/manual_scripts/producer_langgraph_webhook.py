"""
Producer script for LangGraph Simple React Agent with Webhook
Uses the Pulse client directly to schedule LangGraph workflows with webhook delivery.
"""
import sys
import os
import time

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:3001/webhook/langgraph")
    print(f"Connecting to server at {server_url}...")
    print(f"Webhook will be sent to: {webhook_url}")

    # Define the LangGraph workflow configuration
    workflow_config = {
        "agent_type": "react_agent",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_iterations": 10,
        "tools": [
            {
                "name": "web_search",
                "description": "Search the web for information",
                "type": "web_search"
            },
            {
                "name": "calculator",
                "description": "Perform mathematical calculations",
                "type": "calculator"
            }
        ],
        "system_prompt": "You are a helpful AI assistant. Use the available tools to answer questions accurately and efficiently.",
        "memory_type": "buffer",
        "memory_size": 100,
        "user_query": "Analyze the current stock market trends and provide investment recommendations for tech stocks.",
        "expected_output": "Market analysis report with recommendations",
        "webhook_metadata": {
            "callback_type": "market_analysis_complete",
            "notification_email": "trader@example.com"
        }
    }

    print(f"\n🧠🔗 Scheduling LangGraph React Agent Webhook workflow:")
    print(f"   Workflow: market_analyzer")
    print(f"   Query: {workflow_config['user_query'][:60]}...")
    print(f"   Webhook URL: {webhook_url}")

    # Schedule the workflow using the tool's helper method, but with webhook parameters
    # Since the tool doesn't directly support webhooks, we'll use the client directly for webhooks
    from runagent_pulse.client import PulseClient
    client = PulseClient(server_url=server_url)

    payload = {
        "workflow_name": "market_analyzer",
        "workflow_config": workflow_config,
        "execution_framework": "langgraph",
        "webhook_metadata": workflow_config["webhook_metadata"]
    }

    try:
        task = client.schedule(
            schedule_type="langgraph_workflow_webhook",
            when="in 45 seconds",
            payload=payload,
            webhook_url=webhook_url,
            webhook_timeout=300,  # 5 minutes timeout for complex AI tasks
            webhook_retries=2,    # Retry failed webhooks
            metadata={
                "framework": "langgraph",
                "agent_type": "react_agent",
                "execution_mode": "webhook",
                "complexity": "high",
                "estimated_duration": "10-20 minutes",
                "created_by": "producer_langgraph_webhook.py"
            }
        )

        # Get task details
        try:
            task_details = task.get_details()
            task_id = task.task_id

            print(f"\n✅ LangGraph Webhook workflow scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Next execution: {task_details.get('next_execution_iso', task_details.get('next_execution', 'N/A'))}")
            print(f"   Status: {task_details.get('status', 'N/A')}")
            print(f"   Framework: LangGraph React Agent (Webhook)")
            print(f"   Webhook URL: {webhook_url}")
            print(f"   Timeout: 300s, Retries: 2")
            print(f"\n🔗 Webhook will be sent to {webhook_url} upon completion")
            print(f"📊 Dashboard: http://localhost:8000/dashboard")
        except Exception as e:
            task_id = task.task_id
            print(f"\n✅ LangGraph Webhook workflow scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   (Note: Could not fetch full details: {e})")

    except Exception as e:
        print(f"❌ Error scheduling LangGraph webhook workflow: {e}")


if __name__ == "__main__":
    main()
