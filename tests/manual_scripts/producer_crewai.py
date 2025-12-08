"""
Producer script demonstrating CrewAI with the framework-specific tools namespace.
Shows how a CrewAI crew can schedule tasks using runagent_pulse.tools.crewai.
"""
import os

from crewai import Agent, Task, Crew
from runagent_pulse.tools.crewai import PulseClient


def main():

    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        return

    print(f"Connecting to Pulse server at {server_url}...")
    print("Creating CrewAI crew with scheduling capabilities (new tools namespace)...")

    # Create Pulse client and scheduler tool from the crewai namespace
    client = PulseClient(server_url=server_url)
    scheduler_tool = client.ScheduleTaskTool()

    # Create a CrewAI agent with the scheduling tool
    scheduler_agent = Agent(
        role="Meeting Coordinator",
        goal="Schedule and coordinate meetings and events using available tools",
        backstory="You are an experienced administrative assistant who excels at scheduling and coordination.",
        tools=[scheduler_tool],
        verbose=True,
        allow_delegation=False
    )

    # Create a task for the agent to schedule a meeting
    scheduling_task = Task(
        description="""
        Schedule a team meeting for 1 minute from now.

        Use the pulse_scheduler tool to schedule a task with:
        - schedule_type: "team_meeting"
        - when: "in 1 minute"
        - Include metadata about the meeting (participants, agenda, etc.)

        Be specific and use the tool correctly to accomplish this scheduling task.
        """,
        expected_output="Confirmation that the meeting has been scheduled successfully",
        agent=scheduler_agent
    )

    # Create the crew
    crew = Crew(
        agents=[scheduler_agent],
        tasks=[scheduling_task],
        verbose=True
    )

    print("\n👥 CrewAI crew ready!")
    print("The crew has a Meeting Coordinator agent with access to the ScheduleTaskTool.")
    print("\n📝 Starting crew to schedule a meeting...")
    try:
        # Run the crew
        result = crew.kickoff()

        print("\n✅ Crew completed its task!")
        print(f"Result: {result}")

        print("\n💡 Check the Pulse dashboard at http://localhost:8000/dashboard")
        print("   Look for a scheduled 'team_meeting' task created by the crew agent")

    except Exception as e:
        print(f"❌ Error running CrewAI crew: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
