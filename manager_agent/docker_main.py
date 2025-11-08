from fastapi import FastAPI
from pydantic import BaseModel
from .firestore.firestore_session_service import FirestoreSessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part, Blob
from .agent import root_agent
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import requests
import json
import uuid
from datetime import datetime
import io

from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
DATABASE = os.getenv("DATABASE")
BIGQUERY_DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "venture_ai_test_dataset")
BIGQUERY_TABLE_ID = os.getenv("BIGQUERY_TABLE_ID", "pitch_deck_analysis")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") # User needs to set this in .env

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Services ---
session_service = FirestoreSessionService(project=PROJECT_ID, database=DATABASE)
runner = Runner(app_name="venture-ai", agent=root_agent, session_service=session_service)
bigquery_client = bigquery.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)

# --- Helper Functions ---
_bigquery_table_checked = False

def setup_bigquery_table():
    """Creates the BigQuery dataset and table with the correct, comprehensive schema."""
    global _bigquery_table_checked
    if _bigquery_table_checked:
        return

    dataset_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}"
    table_ref_str = f"{dataset_ref_str}.{BIGQUERY_TABLE_ID}"

    try:
        bigquery_client.get_dataset(dataset_ref_str)
    except NotFound:
        print(f"BigQuery Dataset '{BIGQUERY_DATASET_ID}' not found, creating it...")
        dataset = bigquery.Dataset(dataset_ref_str)
        dataset.location = "US"
        bigquery_client.create_dataset(dataset, timeout=30)

    try:
        bigquery_client.get_table(table_ref_str)
        print(f"BigQuery Table '{BIGQUERY_TABLE_ID}' already exists.")
    except NotFound:
        print(f"BigQuery Table '{BIGQUERY_TABLE_ID}' not found, creating it...")
        schema = [
            bigquery.SchemaField("analysis_id", "STRING"),
            bigquery.SchemaField("user_id", "STRING"),
            bigquery.SchemaField("generated_pdf_url", "STRING"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("tech_field", "STRING"),
            bigquery.SchemaField("company_website", "STRING"),
            bigquery.SchemaField("date", "STRING"),
            bigquery.SchemaField("author", "STRING"),
            bigquery.SchemaField("introduction", "STRING"),
            bigquery.SchemaField("problem", "STRING"),
            bigquery.SchemaField("product_description", "STRING"),
            bigquery.SchemaField("business_model", "STRING"),
            bigquery.SchemaField("market_competition", "STRING"),
            bigquery.SchemaField("opportunity", "STRING"),
            bigquery.SchemaField("market_size_tam", "STRING"),
            bigquery.SchemaField("market_size_som", "STRING"),
            bigquery.SchemaField("market_growth_rate", "STRING"),
            bigquery.SchemaField("impact_metrics", "STRING"),
            bigquery.SchemaField("customer_feedback", "STRING"),
            bigquery.SchemaField("founders", "STRING"),
            bigquery.SchemaField("team_strengths", "STRING"),
            bigquery.SchemaField("key_strengths", "STRING"),
            bigquery.SchemaField("round_size", "STRING"),
            bigquery.SchemaField("use_of_funds", "STRING"),
            bigquery.SchemaField("growth_trajectory", "STRING"),
            bigquery.SchemaField("recommendation", "STRING"),
            bigquery.SchemaField("justification", "STRING"),
            bigquery.SchemaField("technical_risk", "STRING"),
        ]
        table = bigquery.Table(table_ref_str, schema=schema)
        bigquery_client.create_table(table)
        print(f"Table '{BIGQUERY_TABLE_ID}' created successfully.")
    _bigquery_table_checked = True

def generate_pdf_from_json(json_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    def add_section(title, content, level=1):
        if title:
            style = styles["Heading1"] if level == 1 else styles["Heading2"]
            story.append(Paragraph(title, style))
        story.append(Spacer(1, 8))
        if isinstance(content, dict):
            for k, v in content.items():
                add_section(k.replace("_", " ").title(), v, level + 1)
        elif isinstance(content, list):
            for item in content:
                add_section(None, item, level + 1)
        else:
            story.append(Paragraph(str(content), styles["Normal"]))
            story.append(Spacer(1, 6))
    add_section("Investment Memo", json_data.get("investment_memo", json_data))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# --- Pydantic Models ---
class CreateSessionRequest(BaseModel):
    user_id: str
    initial_state: Optional[Dict[str, Any]] = None

class QueryRequest(BaseModel):
    session_id: str
    user_id: str
    message: str

class GenerateInvestmentAnalysisRequest(BaseModel):
    user_id: str
    session_id: str
    pdf_url: str
    tech_field: str
    short_description: str
    company_website: Optional[str] = None
    prompt: Optional[str] = "Analyze this pitch deck and return a comprehensive investment memo based on your defined output schema."

class InvestorQueryRequest(BaseModel):
    session_id: str
    user_id: str
    prompt: str
    analysis_id: str

class FollowupQuestionRequest(BaseModel):
    user_id: str
    session_id: str

# --- API Endpoints ---
@app.on_event("startup")
async def startup_event():
    setup_bigquery_table()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/create_session")
async def create_session(request: CreateSessionRequest):
    """Creates a new session or reuses an existing one and returns the session ID and state."""
    
    print(f"Checking for existing sessions for user '{request.user_id}'...")
    list_sessions_response = await session_service.list_sessions(app_name="venture-ai", user_id=request.user_id)
    
    session_id = None
    session_state = {}

    if list_sessions_response and list_sessions_response.sessions:
        remote_session = list_sessions_response.sessions[0]
        session_id = remote_session.id
        session_state = remote_session.state
        print(f"Found existing session with ID: {session_id}")
    else:
        print(f"No existing sessions for user '{request.user_id}'. Creating a new one.")
        new_session = await session_service.create_session(user_id=request.user_id, state=request.initial_state)
        session_id = new_session.id
        session_state = new_session.state
        print(f"Created new session with ID: {session_id}")
    
    if not session_id:
         raise Exception("Failed to get or create a session ID.")

    response_data = json.dumps({"session_id": session_id, "state": session_state})
    return JSONResponse(content=response_data)


@app.post("/query")
async def query(request: QueryRequest):
    """Runs a query against the agent and returns the response."""
    new_message = Content(role="user", parts=[Part(text=request.message)])
    
    response_chunks = []
    async for event in runner.run_async(
        user_id=request.user_id,
        session_id=request.session_id,
        new_message=new_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_chunks.append(part.text)

    if not response_chunks:
        final_response = ""
    else:
        final_response = response_chunks[-1]

    response_data = json.dumps({"agent_response": final_response})
    return JSONResponse(content=response_data)

@app.post("/generate_investment_analysis")
async def generate_investment_analysis(request: GenerateInvestmentAnalysisRequest):
    """
    Runs an investment analysis on a pitch deck and returns the analysis as JSON.
    """
    analysis_id = str(uuid.uuid4())

    # Download the PDF from the URL
    response = requests.get(request.pdf_url)
    response.raise_for_status()
    pdf_data = response.content

    # Create the message for the agent
    message_parts = [
        Part(inline_data=Blob(data=pdf_data, mime_type="application/pdf")),
        Part(text=request.prompt)
    ]
    new_message = Content(role="user", parts=message_parts)

    # Run the query against the agent
    response_chunks = []
    async for event in runner.run_async(
        user_id=request.user_id,
        session_id=request.session_id,
        new_message=new_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_chunks.append(part.text)

    if not response_chunks:
        response_data = json.dumps({"error": "Agent returned no response."})
        return JSONResponse(content={"response_data": response_data})

    final_response_text = response_chunks[-1]
    
    if final_response_text.strip().startswith("```json"):
        final_response_text = final_response_text[final_response_text.find('{'):final_response_text.rfind('}')+1]

    try:
        analysis_data = json.loads(final_response_text)
    except json.JSONDecodeError as e:
        response_data = json.dumps({"error": f"Failed to decode JSON from agent response: {e}", "raw_response": final_response_text})
        return JSONResponse(content={"response_data": response_data})

    # Generate and upload PDF
    pdf_bytes = generate_pdf_from_json(analysis_data)
    if not GCS_BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME environment variable not set.")
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(f"investment_memos/{analysis_id}.pdf")
    blob.upload_from_string(pdf_bytes, content_type='application/pdf')
    blob.make_public()
    generated_pdf_url = blob.public_url

    # Insert into BigQuery
    table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"
    memo_data = analysis_data.get("investment_memo", analysis_data)
    row_to_insert = {
        "analysis_id": analysis_id,
        "user_id": request.user_id,
        "generated_pdf_url": generated_pdf_url,
        "company_name": memo_data.get("company_name"),
        "tech_field": request.tech_field,
        "company_website": request.company_website,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": "VentureAI Agent",
        "introduction": memo_data.get("summary"),
        "problem": memo_data.get("problem_definition"),
        "product_description": memo_data.get("solution_description"),
        "business_model": memo_data.get("business_model"),
        "market_competition": memo_data.get("competitive_advantage"),
    }
    if team_analysis := memo_data.get("team_analysis"):
        row_to_insert["founders"] = team_analysis.get("founders")
        row_to_insert["team_strengths"] = team_analysis.get("background_summary")
        row_to_insert["key_strengths"] = team_analysis.get("strengths")
    if market_opportunity := memo_data.get("market_opportunity"):
        row_to_insert["market_size_tam"] = market_opportunity.get("market_size_tam")
        row_to_insert["market_size_som"] = market_opportunity.get("market_size_sam")
        row_to_insert["market_growth_rate"] = market_opportunity.get("market_growth_rate")
        row_to_insert["opportunity"] = market_opportunity.get("analysis")
    if traction := memo_data.get("traction"):
        row_to_insert["impact_metrics"] = traction.get("metrics")
        row_to_insert["customer_feedback"] = traction.get("customer_feedback")
    if financials := memo_data.get("financials"):
        row_to_insert["round_size"] = str(financials.get("funding_ask_inr"))
        row_to_insert["use_of_funds"] = financials.get("use_of_funds")
        row_to_insert["growth_trajectory"] = financials.get("projections_summary")
    if investment_recommendation := memo_data.get("investment_recommendation"):
        row_to_insert["recommendation"] = investment_recommendation.get("recommendation")
        row_to_insert["justification"] = investment_recommendation.get("justification")
        row_to_insert["technical_risk"] = investment_recommendation.get("risks")
    for key, value in row_to_insert.items():
        if isinstance(value, (list, dict)):
            row_to_insert[key] = json.dumps(value)
    
    errors = bigquery_client.insert_rows_json(table_ref_str, [row_to_insert])
    if errors:
        raise Exception(f"BigQuery insertion failed: {errors}")

    # Update session state
    state_delta = {
        "analysis_id": analysis_id,
        "generated_pdf_url": generated_pdf_url,
        "tech_field": request.tech_field,
        "company_website": request.company_website,
        "short_description": request.short_description,
        "pitch_deck_url": request.pdf_url
    }
    await session_service.update_session_state(request.session_id, state_delta)

    response_data = json.dumps({"message": "Analysis complete", "analysis_id": analysis_id, "generated_pdf_url": generated_pdf_url})
    return JSONResponse(content=response_data)

@app.get("/get_investor_dashboard_data")
async def get_investor_dashboard_data():
    """
    Fetches all rows from the BigQuery pitch deck analysis table for the investor dashboard.
    """
    table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"
    query = f"SELECT * FROM `{table_ref_str}`"
    
    query_job = bigquery_client.query(query)
    rows = [dict(row) for row in query_job]
    
    response_data = json.dumps(rows, default=str)
    return JSONResponse(content=response_data)

@app.post("/investor_query")
async def investor_query(request: InvestorQueryRequest):
    """
    Handles an investor query by updating the session state and running the query against the agent.
    """
    # Update session state with analysis_id
    state_delta = {"id_to_analyse": request.analysis_id}
    await session_service.update_session_state(request.session_id, state_delta)

    # Create the message for the agent
    new_message = Content(role="user", parts=[Part(text=request.prompt)])

    # Run the query against the agent
    response_chunks = []
    async for event in runner.run_async(
        user_id=request.user_id,
        session_id=request.session_id,
        new_message=new_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_chunks.append(part.text)

    if not response_chunks:
        final_response = ""
    else:
        final_response = "".join(response_chunks)
    
    response_data = json.dumps({"message": "Query processed", "agent_response": final_response})
    return JSONResponse(content=response_data)

@app.post("/followup_question")
async def followup_question(request: FollowupQuestionRequest):
    """
    Generates follow-up questions for the founder based on the analysis.
    """
    prompt = "provide me follow up questins for the founder based on the analysis. Also provide the questions as a json."
    new_message = Content(role="user", parts=[Part(text=prompt)])

    response_chunks = []
    async for event in runner.run_async(
        user_id=request.user_id,
        session_id=request.session_id,
        new_message=new_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_chunks.append(part.text)

    if not response_chunks:
        full_response_text = ""
    else:
        full_response_text = "".join(response_chunks)

    response_data = json.dumps({"message": "Follow-up questions generated", "agent_response": full_response_text})
    return JSONResponse(content=response_data)