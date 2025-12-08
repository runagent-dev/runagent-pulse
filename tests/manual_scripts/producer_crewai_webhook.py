"""
Producer script for CrewAI Multi-Agent System with Webhook
Uses the PulseSchedulerTool to schedule CrewAI missions with webhook delivery
"""
import sys
import os
import time

# Add root to path so we can import SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from runagent_pulse.client import PulseClient


def main():
    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:3001/webhook/crewai")
    print(f"Connecting to server at {server_url}...")
    print(f"Webhook will be sent to: {webhook_url}")

    # For webhooks, we need to use the client directly since the tool doesn't support webhook parameters yet
    client = PulseClient(server_url=server_url)

    # Define the CrewAI crew configuration for a business analysis project
    crew_config = {
        "crew_name": "Business Intelligence Team",
        "agents": [
            {
                "name": "Market Analyst",
                "role": "Senior Market Research Analyst",
                "goal": "Analyze market trends and provide insights on business opportunities",
                "backstory": "Expert market analyst with deep knowledge of industry trends and competitive analysis.",
                "model": "gpt-4",
                "temperature": 0.4,
                "tools": ["market_data", "trend_analyzer", "competitor_research"],
                "verbose": True
            },
            {
                "name": "Business Strategist",
                "role": "Strategic Business Consultant",
                "goal": "Develop strategic recommendations based on market analysis",
                "backstory": "Experienced strategist who helps businesses make data-driven decisions.",
                "model": "gpt-4",
                "temperature": 0.5,
                "tools": ["strategy_planner", "risk_assessor", "roi_calculator"],
                "verbose": True
            },
            {
                "name": "Report Writer",
                "role": "Professional Business Report Writer",
                "goal": "Create clear, actionable business reports and presentations",
                "backstory": "Skilled communicator who transforms complex analysis into compelling business narratives.",
                "model": "gpt-4",
                "temperature": 0.6,
                "tools": ["document_formatter", "visualization_creator"],
                "verbose": False
            }
        ],
        "tasks": [
            {
                "description": "Analyze the current market trends in the electric vehicle industry",
                "agent": "Market Analyst",
                "expected_output": "Comprehensive market analysis report with trends, opportunities, and challenges",
                "context": ["Focus on EV market growth, key players, consumer adoption, and technological advancements"],
                "output_file": "market_analysis.md"
            },
            {
                "description": "Develop strategic recommendations for entering the EV market based on the analysis",
                "agent": "Business Strategist",
                "expected_output": "Strategic plan with market entry recommendations, competitive positioning, and risk assessment",
                "context": ["Use market analysis to develop actionable business strategies"],
                "output_file": "strategic_plan.md"
            },
            {
                "description": "Create a professional executive summary and presentation for stakeholders",
                "agent": "Report Writer",
                "expected_output": "Executive summary report and presentation slides ready for stakeholder review",
                "context": ["Compile findings into a clear, professional format for decision-makers"],
                "output_file": "executive_summary.pdf"
            }
        ],
        "process": "sequential",
        "verbose": True,
        "memory": True,
        "max_rpm": 10,
        "project_name": "Electric Vehicle Market Strategy",
        "project_description": "Complete market analysis and strategic planning for EV market entry using multi-agent crew",
        "deliverables": [
            "market_analysis.md",
            "strategic_plan.md",
            "executive_summary.pdf",
            "presentation_slides.pptx"
        ],
        "priority": "critical",
        "deadline": "2024-12-15",
        "webhook_metadata": {
            "callback_type": "crewai_project_complete",
            "client_notification": "stakeholders@example.com",
            "project_manager": "pm@example.com",
            "slack_channel": "#strategy-projects"
        }
    }

    # Prepare payload for webhook scheduling
    task_payload = {
        "mission_name": "Electric Vehicle Market Strategy",
        "crew_config": crew_config,
        "execution_framework": "crewai",
        "webhook_metadata": crew_config["webhook_metadata"]
    }

    print(f"\n👥🔗 Scheduling CrewAI Multi-Agent Webhook mission:")
    print(f"   Crew: {crew_config['crew_name']}")
    print(f"   Agents: {len(crew_config['agents'])}")
    print(f"   Tasks: {len(crew_config['tasks'])}")
    print(f"   Project: {crew_config['project_name']}")
    print(f"   Priority: {crew_config['priority']}")
    print(f"   Webhook URL: {webhook_url}")

    try:
        task = client.schedule(
            schedule_type="crewai_mission_webhook",
            when="in 120 seconds",  # Schedule to run in 2 minutes (complex task)
            payload=task_payload,
            webhook_url=webhook_url,
            webhook_timeout=1800,  # 30 minutes timeout for complex multi-agent tasks
            webhook_retries=3,     # More retries for critical business tasks
            metadata={
                "framework": "crewai",
                "agent_count": len(crew_config['agents']),
                "task_count": len(crew_config['tasks']),
                "execution_mode": "webhook",
                "complexity": "critical",
                "priority": crew_config['priority'],
                "estimated_duration": "30-60 minutes",
                "process_type": crew_config['process'],
                "created_by": "producer_crewai_webhook.py"
            }
        )

        # Get task details
        try:
            task_details = task.get_details()
            task_id = task.task_id

            print(f"\n✅ CrewAI Webhook mission scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Next execution: {task_details.get('next_execution_iso', task_details.get('next_execution', 'N/A'))}")
            print(f"   Status: {task_details.get('status', 'N/A')}")
            print(f"   Framework: CrewAI Multi-Agent (Webhook)")
            print(f"   Crew: {crew_config['crew_name']}")
            print(f"   Process: {crew_config['process']}")
            print(f"   Priority: {crew_config['priority']}")
            print(f"   Webhook URL: {webhook_url}")
            print(f"   Timeout: 1800s, Retries: 3")
            print(f"\n🔗 Webhook will be sent to {webhook_url} upon completion")
            print(f"📊 Dashboard: http://localhost:8000/dashboard")
        except Exception as e:
            task_id = task.task_id
            print(f"\n✅ CrewAI Webhook mission scheduled successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Crew: {crew_config['crew_name']}")
            print(f"   (Note: Could not fetch full details: {e})")

    except Exception as e:
        print(f"❌ Error scheduling CrewAI webhook mission: {e}")


if __name__ == "__main__":
    main()
