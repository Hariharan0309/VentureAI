from google.adk.agents import Agent
from google.adk.tools import google_search

web_research_analyst_agent = Agent(
    name="web_research_analyst",
    model="gemini-2.5-pro",
    description="Researches and verifies information from a pitch deck using Google.",
    instruction="""
    You are a research analyst. You will be given a JSON object containing claims from a startup's pitch deck.
    Your task is to use the google_search tool to independently verify these claims and find additional, publicly available information.
    Focus on:
    - Verifying the market size.
    - Researching the named competitors and finding any unmentioned ones.
    - Finding the professional backgrounds of the founders.
    - Looking for any news articles or public data related to the company's traction.
    Output your findings as a new, enriched JSON object. Clearly cite your sources with URLs in your output.
    """,
    tools=[google_search],
)