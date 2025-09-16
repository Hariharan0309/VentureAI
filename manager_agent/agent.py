from google.adk.agents import Agent
from sub_agents.pitch_analyzer import pitch_analyzer_agent

root_agent = Agent(
    name="manager_agent",
    model="gemini-2.5-pro",
    description="VentureAI Manager Agent",
    instruction="""
    You are the central Manager Agent for the VentureAI platform. Your primary role is to act as a helpful assistant for venture capitalists and startup founders. Your goal is to provide insightful information and analysis on startups, market trends, and investment opportunities.
    When you need to analyze a pitch deck, delegate the task to the 'pitch_analyzer_agent' sub-agent.
    """,
    sub_agents = [pitch_analyzer_agent]
)

