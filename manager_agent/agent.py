from google.adk.agents import Agent
from sub_agents.pitch_deck_extractor import pitch_deck_extractor_agent
from sub_agents.web_research_analyst import web_research_analyst_agent
from sub_agents.report_generation_agent import report_generation_agent


root_agent = Agent(
    name="manager_agent",
    model="gemini-2.5-pro",
    description="Orchestrates the analysis of a pitch deck from extraction to final report.",
    instruction="""
    You are the manager of a multi-agent system for analyzing startup pitch decks.
    Your goal is to produce a comprehensive investment memo. You will follow a strict three-step sequence.

    When you receive a pitch deck PDF, you must perform the following steps in order:

    1.  **EXTRACT:** Call the 'pitch_deck_extractor' sub-agent. Pass the pitch deck to it. Its output will be a JSON object of the claims made in the deck.

    2.  **RESEARCH:** Call the 'web_research_analyst' sub-agent. Pass the JSON object from the previous step to it. Its output will be an enriched JSON object with verified data and web findings.

    3.  **GENERATE:** Call the 'report_generation_agent' sub-agent. Pass *both* the original JSON from step 1 and the enriched JSON from step 2 to it. Its output will be the final report in JSON format.

    Your final response to the user should be only the JSON object produced by the 'report_generation_agent'. Do not add any other text.
    """,
    sub_agents=[pitch_deck_extractor_agent,web_research_analyst_agent, report_generation_agent],
)

