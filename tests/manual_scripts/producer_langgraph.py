"""
Producer script demonstrating LangGraph React Agent using the framework-specific tools namespace.
Shows how a LangGraph agent can schedule tasks using runagent_pulse.tools.langgraph.
"""
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from runagent_pulse.tools.langgraph import PulseClient


def main():

    server_url = os.getenv("PULSE_SERVER_URL", "http://localhost:8000")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        return

    print(f"Connecting to Pulse server at {server_url}...")
    print("Creating LangGraph React Agent with scheduling capabilities (new tools namespace)...")

    # Create Pulse client and scheduler tool from the langgraph namespace
    pulse_tools = PulseClient(server_url=server_url)
    scheduler_tool = pulse_tools.ScheduleTaskTool()

    # Create LangGraph agent with the scheduler tool
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        api_key=openai_api_key
    )

    # Create React Agent with scheduling tool
    agent = create_react_agent(llm, tools=[scheduler_tool])

    print("\n🤖 LangGraph Agent ready!")
    print("The agent has access to the PulseSchedulerTool and will use it to schedule tasks.")
    # Define the task for the agent
    user_instruction = """
    You are a helpful AI assistant with access to a task scheduling tool.

    Your task is to schedule a meeting for me. Please use the available scheduling tool to:
    1. Schedule a "team_meeting" task to run 1 minute from now
    2. Include appropriate metadata about the meeting

    Use the pulse_scheduler tool to accomplish this. Be specific about the schedule_type and when parameter.
    """

    print(f"\n📝 Asking agent to schedule a meeting...")
    print(f"Instruction: {user_instruction.strip()}")

    try:
        # Run the agent
        result = agent.invoke({
            "messages": [HumanMessage(content=user_instruction)]
        })

        print("\n✅ Agent completed its task!")
        print(f"Response: {result['messages'][-1].content}")

        # The agent should have used the tool to schedule the meeting
        # Let's check if any tasks were scheduled by looking at the tool calls
        if hasattr(result['messages'][-1], 'tool_calls') and result['messages'][-1].tool_calls:
            print("\n🔧 Tool calls made:")
            for tool_call in result['messages'][-1].tool_calls:
                print(f"   - {tool_call['name']}: {tool_call['args']}")

        print("\n💡 Check the Pulse dashboard at http://localhost:8000/dashboard")
        print("   Look for a 'pulse_scheduler' task that was scheduled by the agent")

    except Exception as e:
        print(f"❌ Error running LangGraph agent: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
