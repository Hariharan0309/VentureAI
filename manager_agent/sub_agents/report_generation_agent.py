from google.adk.agents import Agent
import pydantic
from typing import List, Optional

# --- Pydantic Schemas for Structured Output ---

class TeamAnalysis(pydantic.BaseModel):
    """Analysis of the founding team."""
    founders: List[str] = pydantic.Field(description="Names of the founders.")
    background_summary: str = pydantic.Field(description="Summary of the team's experience and domain expertise.")
    strengths: List[str] = pydantic.Field(description="Key strengths of the founding team.")

class MarketOpportunity(pydantic.BaseModel):
    """Analysis of the market opportunity."""
    market_size_tam: str = pydantic.Field(description="Total Addressable Market (TAM).")
    market_size_sam: Optional[str] = pydantic.Field(description="Serviceable Addressable Market (SAM).")
    market_growth_rate: Optional[str] = pydantic.Field(description="The growth rate of the target market.")
    analysis: str = pydantic.Field(description="Analyst's commentary on the market opportunity.")

class Traction(pydantic.BaseModel):
    """Analysis of the company's traction."""
    metrics: str = pydantic.Field(description="Key traction metrics like revenue, user numbers, or engagement.")
    customer_feedback: Optional[str] = pydantic.Field(description="Summary of customer feedback or testimonials.")

class Financials(pydantic.BaseModel):
    """Summary of the company's financials and funding request."""
    funding_ask_inr: int = pydantic.Field(description="How much funding is being requested, in INR.")
    use_of_funds: str = pydantic.Field(description="How the requested funds will be used.")
    projections_summary: Optional[str] = pydantic.Field(description="A summary of their financial projections.")

class InvestmentRecommendation(pydantic.BaseModel):
    """The final investment recommendation."""
    recommendation: str = pydantic.Field(description="The analyst's final recommendation (e.g., 'High Conviction: Invest', 'Consider', 'Pass').")
    justification: str = pydantic.Field(description="The reasoning behind the recommendation.")
    risks: List[str] = pydantic.Field(description="Potential risks associated with the investment.")

class InvestmentMemo(pydantic.BaseModel):
    """The final, structured investment memo."""
    company_name: str = pydantic.Field(description="Name of the startup.")
    summary: str = pydantic.Field(description="A one-paragraph executive summary of the investment opportunity.")
    team_analysis: TeamAnalysis
    problem_definition: str = pydantic.Field(description="A clear description of the problem the startup is solving.")
    solution_description: str = pydantic.Field(description="A clear description of the startup's solution.")
    market_opportunity: MarketOpportunity
    traction: Traction
    business_model: str = pydantic.Field(description="How the company makes money (e.g., SaaS, transaction fees).")
    competitive_advantage: str = pydantic.Field(description="The company's unique advantage over competitors.")
    financials: Financials
    investment_recommendation: InvestmentRecommendation

# --- Agent Definition ---

report_generation_agent = Agent(
    name="report_generation_agent",
    model="gemini-2.5-pro",
    description="Synthesizes pitch deck data and web research into a final investment memo.",
    instruction="""
    You are a senior VC partner. You will be given two JSON objects:
    1. The original claims extracted from a pitch deck.
    2. The enriched data and verifications from a research analyst.

    Your task is to synthesize all of this information into a final, comprehensive investment memo.
    Where the internal claims and external research differ, you must highlight the discrepancy in your analysis.
    Your final output must be a single, clean JSON object that strictly adheres to the provided output schema.
    """,
    tools=[],
    output_schema=InvestmentMemo,
)