from google.adk.agents import Agent, SequentialAgent
from sub_agents.pitch_deck_extractor import pitch_deck_extractor_agent
from sub_agents.web_research_analyst import web_research_analyst_agent
from sub_agents.report_generation_agent import report_generation_agent
from sub_agents.invester_query_agent import investor_query_agent
from sub_agents.followup_questions_agent import followup_questions_agent



investment_memo_generation_agent = SequentialAgent(
    name="inestmemo_generation_agent",
    sub_agents=[pitch_deck_extractor_agent, web_research_analyst_agent, report_generation_agent],
    description="Extracts a sequence of pitch deck extraction, web research, and report generation.",
)

# root_agent = investment_memo_generation_agent

root_agent = Agent(
    name="manager_agent",
    model="gemini-2.5-pro",
    description="Orchestrates the analysis of a pitch deck from extraction to final report and answers investor questions.",
    instruction="""
    You are a manager agent responsible for delegating tasks to the appropriate sub-agent.

    **Workflow:**

    1.  **Analyze Input and User Intent:**
        *   Examine the user's request to determine their primary goal.
        *   If the user provides a PDF file AND their request includes keywords like "analyze", "analysis", "investment memo", or "report", it is a **Pitch Deck Analysis Task**.
        *   If the user asks a question in plain text, it is an **Investor Question Task**.
        *   If the user's request includes keywords like "follow-up questions", "generate questions", or "questions for founder", it is a **Follow-up Questions Task** (e.g., "generate follow-up questions for the founder").

    2.  **Delegate Task:**
        *   For a **Pitch Deck Analysis Task**, delegate the entire task to the `investment_memo_generation_agent`. This agent will handle the complete analysis and generate the investment memo.
        *   For an **Investor Question Task**, delegate the question to the `investor_query_agent`. This agent will query the database to find the answer.
        *   For a **Follow-up Questions Task**, delegate the request to the `followup_questions_agent`. This agent will generate challenging follow-up questions for the founder.

    **Output:**

    *   For pitch deck analysis, return only the JSON output from the `investment_memo_generation_agent`.
    *   For investor questions, return the natural language answer from the `investor_query_agent`.
    *   For follow-up questions, return the JSON output from the `followup_questions_agent`.
    """,
    sub_agents=[investment_memo_generation_agent, investor_query_agent, followup_questions_agent],
)
