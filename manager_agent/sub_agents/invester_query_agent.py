from google.adk.agents import Agent
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
    analysis_id = tool_context.state.get('id_to_analyse')
    if not analysis_id:
        raise ValueError("id_to_analyse not found in the session state.")

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

investor_query_agent = Agent(
    name="investor_query_agent",
    model="gemini-2.5-pro",
    description="A sub-agent that answers investor questions based on a specific analysis.",
    instruction="""
    You are an expert analyst. Your task is to answer investor questions based on the data provided to you.

    **Workflow:**

    1.  **Receive Request:** You will be called with a user's question.

    2.  **Fetch Data:** Use the `get_analysis_data` tool to retrieve the analysis data from the database. The `analysis_id` is automatically retrieved from the session state.

    3.  **Analyze and Answer:** Analyze the retrieved data and formulate a clear, concise answer to the user's question. If the data contains an error, inform the user.

    **Output:**

    *   Return a natural language answer to the user's question.
    """,
    tools=[get_analysis_data]
)
