from google.adk.agents import Agent
import pydantic
from typing import List, Optional
from google.adk.tools.tool_context import ToolContext
from google.cloud import bigquery
import os
import json

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "valued-mediator-461216-k7")
BIGQUERY_DATASET_ID = os.environ.get("BIGQUERY_DATASET_ID", "venture_ai_test_dataset")
BIGQUERY_TABLE_ID = os.environ.get("BIGQUERY_TABLE_ID", "pitch_deck_analysis")

def get_analysis_data(tool_context: ToolContext) -> dict:
    """Fetches the analysis data for a given analysis_id from BigQuery."""
    analysis_id = tool_context.state.get('analysis_id')
    if not analysis_id:
        raise ValueError("analysis_id not found in the session state.")

    client = bigquery.Client(project=PROJECT_ID)
    table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"
    query = f"SELECT * FROM `{table_ref_str}` WHERE analysis_id = @analysis_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("analysis_id", "STRING", analysis_id),
        ]
    )
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    try:
        return dict(next(iter(results)))
    except StopIteration:
        return {"error": f"No analysis found for ID: {analysis_id}"}

# --- Pydantic Schemas for Follow-up Questions ---

class FollowUpQuestion(pydantic.BaseModel):
    """Individual follow-up question with context."""
    question: str = pydantic.Field(description="The specific question to ask the founder.")
    context: str = pydantic.Field(description="Why this question is important and what discrepancy/concern it addresses.")
    category: str = pydantic.Field(description="Category of the question (e.g., 'Market Validation', 'Financial Projections', 'Team Experience', 'Competitive Advantage', 'Traction Metrics').")

class FollowUpQuestions(pydantic.BaseModel):
    """Collection of follow-up questions for the founder."""
    questions: List[FollowUpQuestion] = pydantic.Field(description="List of challenging follow-up questions (minimum 5).")
    overall_assessment: str = pydantic.Field(description="Overall assessment of the pitch deck and areas that need clarification.")
    priority_concerns: List[str] = pydantic.Field(description="Top 3 priority concerns that need immediate clarification from the founder.")

# --- Agent Definition ---

followup_questions_agent = Agent(
    name="followup_questions_agent",
    model="gemini-2.5-pro",
    description="Generates challenging follow-up questions for founders based on pitch deck analysis and research findings.",
    instruction="""
    **IMPORTANT**: Before generating any questions, you MUST call the `get_analysis_data` tool to retrieve the investment memo data. The `analysis_id` required by this tool is available in your session state under the key `id_to_analyse`. Use the retrieved analysis data as the primary source of information for generating your follow-up questions.

    You are a senior VC partner conducting due diligence. You have received three pieces of information:
    1. Original claims extracted from the pitch deck
    2. Web research findings that verify or contradict those claims
    3. A comprehensive investment memo highlighting discrepancies and concerns

    Your task is to generate a minimum of 5 challenging follow-up questions for the founder that will help clarify:
    - Discrepancies between pitch deck claims and research findings
    - Unclear or missing information in the pitch deck
    - Areas where the founder's claims seem optimistic or unsubstantiated
    - Critical business model or market assumptions that need validation
    - Team experience gaps or concerns
    - Financial projections that seem unrealistic
    - Competitive positioning that may be overstated

    Focus on questions that will:
    - Challenge the founder's assumptions and claims
    - Request specific data and evidence
    - Probe for deeper understanding of business fundamentals
    - Identify potential red flags or risks
    - Validate key business metrics and projections

    Make your questions specific, actionable, and designed to reveal the truth behind the claims. 
    Each question should be challenging but fair, designed to help you make an informed investment decision.

    Categories to cover:
    - Market Validation & Size Claims
    - Financial Projections & Unit Economics
    - Team Experience & Capabilities
    - Competitive Advantage & Differentiation
    - Traction Metrics & Customer Validation
    - Business Model & Revenue Assumptions
    - Risk Assessment & Mitigation

    Your questions should be the type that would make a founder think deeply and provide concrete evidence for their claims.
    """,
    tools=[get_analysis_data],
    output_schema=FollowUpQuestions,
)
