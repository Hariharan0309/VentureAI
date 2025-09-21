from firebase_functions import https_fn, firestore_fn
from firebase_functions.options import set_global_options, MemoryOption
from firebase_admin import initialize_app, firestore, storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

import os
import vertexai
from vertexai import agent_engines, generative_models
from vertexai.generative_models import Part, Content
import json
import requests
from datetime import datetime

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "valued-mediator-461216-k7")
LOCATION = os.environ.get("FUNCTION_REGION", "us-central1")
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "2175876336764059648")
DATABASE = "ventureai"

# BigQuery Configuration
BIGQUERY_DATASET_ID = os.environ.get("BIGQUERY_DATASET_ID", "venture_ai_test_dataset")
BIGQUERY_TABLE_ID = os.environ.get("BIGQUERY_TABLE_ID", "pitch_deck_analysis") # Use a new table version
BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID = os.environ.get("BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID", "followup_questions")

# Firestore Configuration
SESSIONS_COLLECTION = "adk_sessions"
# --------------------

# --- Initialization ---
initialize_app()
set_global_options(max_instances=10, memory=MemoryOption.GB_1, timeout_sec=660)

_remote_app = None
_db = None
_bigquery_table_checked = False

def get_remote_app():
    global _remote_app
    if _remote_app is None:
        print("Initializing Vertex AI client...")
        engine_resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
        _remote_app = agent_engines.get(engine_resource_name)
        print("Vertex AI client initialized.")
    return _remote_app

def get_firestore_client():
    global _db
    if _db is None:
        print("Initializing Firestore client...")
        _db = firestore.Client(project=PROJECT_ID, database=DATABASE)
        print("Firestore client initialized.")
    return _db

def setup_bigquery_table():
    """Creates the BigQuery dataset and table with the correct, comprehensive schema."""
    client = bigquery.Client(project=PROJECT_ID)
    dataset_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}"
    table_ref_str = f"{dataset_ref_str}.{BIGQUERY_TABLE_ID}"

    try:
        client.get_dataset(dataset_ref_str)
    except NotFound:
        print(f"BigQuery Dataset '{BIGQUERY_DATASET_ID}' not found, creating it...")
        dataset = bigquery.Dataset(dataset_ref_str)
        dataset.location = "US"
        client.create_dataset(dataset, timeout=30)

    try:
        client.get_table(table_ref_str)
        print(f"BigQuery Table '{BIGQUERY_TABLE_ID}' already exists.")
    except NotFound:
        print(f"BigQuery Table '{BIGQUERY_TABLE_ID}' not found, creating it...")
        schema = [
            bigquery.SchemaField("analysis_id", "STRING"),
            bigquery.SchemaField("user_id", "STRING"), # Added user_id
            bigquery.SchemaField("generated_pdf_url", "STRING"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("tech_field", "STRING"),
            bigquery.SchemaField("company_website", "STRING"),
            bigquery.SchemaField("date", "STRING"),
            bigquery.SchemaField("author", "STRING"),
            bigquery.SchemaField("introduction", "STRING"), # from summary
            bigquery.SchemaField("problem", "STRING"), # from problem_definition
            bigquery.SchemaField("product_description", "STRING"), # from solution_description
            bigquery.SchemaField("business_model", "STRING"), # Added business_model
            bigquery.SchemaField("market_competition", "STRING"), # from competitive_advantage
            bigquery.SchemaField("opportunity", "STRING"), # from market_opportunity.analysis
            bigquery.SchemaField("market_size_tam", "STRING"),
            bigquery.SchemaField("market_size_som", "STRING"),
            bigquery.SchemaField("market_growth_rate", "STRING"),
            bigquery.SchemaField("impact_metrics", "STRING"), # from traction.metrics
            bigquery.SchemaField("customer_feedback", "STRING"),
            bigquery.SchemaField("founders", "STRING"),
            bigquery.SchemaField("team_strengths", "STRING"), # from team_analysis.background_summary
            bigquery.SchemaField("key_strengths", "STRING"), # from team_analysis.strengths
            bigquery.SchemaField("round_size", "STRING"), # from financials.funding_ask_inr
            bigquery.SchemaField("use_of_funds", "STRING"),
            bigquery.SchemaField("growth_trajectory", "STRING"), # from financials.projections_summary
            bigquery.SchemaField("recommendation", "STRING"),
            bigquery.SchemaField("justification", "STRING"),
            bigquery.SchemaField("technical_risk", "STRING"), # from investment_recommendation.risks
        ]
        table = bigquery.Table(table_ref_str, schema=schema)
        client.create_table(table)
        print(f"Table '{BIGQUERY_TABLE_ID}' created successfully.")

def setup_followup_questions_table():
    """Creates the BigQuery table for follow-up questions."""
    client = bigquery.Client(project=PROJECT_ID)
    dataset_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}"
    table_ref_str = f"{dataset_ref_str}.{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}"

    try:
        client.get_table(table_ref_str)
        print(f"BigQuery Table '{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}' already exists.")
    except NotFound:
        print(f"BigQuery Table '{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}' not found, creating it...")
        schema = [
            bigquery.SchemaField("analysis_id", "STRING"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("question_id", "STRING"),
            bigquery.SchemaField("question", "STRING"),
            bigquery.SchemaField("context", "STRING"),
            bigquery.SchemaField("category", "STRING"),
            bigquery.SchemaField("founder_response", "STRING"), # JSON string
            bigquery.SchemaField("response_date", "TIMESTAMP"),
            bigquery.SchemaField("additional_notes", "STRING"),
            bigquery.SchemaField("status", "STRING"), # pending, answered
            bigquery.SchemaField("overall_assessment", "STRING"),
            bigquery.SchemaField("priority_concerns", "STRING"), # JSON string
            bigquery.SchemaField("created_date", "TIMESTAMP"),
            bigquery.SchemaField("last_updated", "TIMESTAMP")
        ]
        table = bigquery.Table(table_ref_str, schema=schema)
        client.create_table(table)
        print(f"Table '{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}' created successfully.")

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

# --------------------

@https_fn.on_request()
def create_session(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to generate investment analysis, now with CORS support.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'user_id' not in request_json:
            return https_fn.Response("Error: Please provide 'user_id' in the JSON body.", status=400, headers=headers)
        
        user_id = request_json['user_id']
        initial_state = request_json.get('state', {})
        remote_app = get_remote_app()

        print(f"Checking for existing sessions for user '{user_id}'...")
        list_sessions_response = remote_app.list_sessions(user_id=user_id)
        
        session_id = None
        session_state = {}

        if list_sessions_response and list_sessions_response.get('sessions'):
            remote_session = list_sessions_response['sessions'][0]
            session_id = remote_session.get('id')
            session_state = remote_session.get('state', {})
            print(f"Found existing session with ID: {session_id}")
        else:
            print(f"No existing sessions for user '{user_id}'. Creating a new one.")
            new_session = remote_app.create_session(user_id=user_id, state=initial_state)
            session_id = new_session.get('id')
            session_state = new_session.get('state', {})
            print(f"Created new session with ID: {session_id}")
        
        if not session_id:
             raise Exception("Failed to get or create a session ID.")

        response_data = json.dumps({"session_id": session_id, "state": session_state})
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in create_session: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request(timeout_sec=540)
def generate_investment_analysis(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to generate investment analysis, now with CORS support.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    global _bigquery_table_checked
    try:
        if not _bigquery_table_checked:
            setup_bigquery_table()
            _bigquery_table_checked = True

        request_json = req.get_json(silent=True)
        required_fields = ['user_id', 'session_id', 'pdf_url', 'tech_field', 'short_description']
        if not request_json or not all(field in request_json for field in required_fields):
                return https_fn.Response(f"Error: Please provide {', '.join(required_fields)}.", status=400, headers=headers)

        user_id = request_json['user_id']
        session_id = request_json['session_id']
        pdf_url = request_json['pdf_url']
        tech_field = request_json['tech_field']
        company_website = request_json.get('company_website')
        short_description = request_json['short_description']
        prompt = request_json.get('prompt', "Analyze this pitch deck and return a comprehensive investment memo based on your defined output schema.")

        analysis_id = str(uuid.uuid4())
        remote_app = get_remote_app()
        
        response = requests.get(pdf_url)
        response.raise_for_status()
        pdf_data = response.content
        
        message_parts = [Part.from_data(data=pdf_data, mime_type="application/pdf"), Part.from_text(prompt)]
        final_message = Content(parts=message_parts, role="user").to_dict()

        print(f"Streaming query to manager_agent for session '{session_id}'...")
        response_chunks = []
        for event in remote_app.stream_query(user_id=user_id, session_id=session_id, message=final_message):
            if event.get('content') and event.get('content').get('parts'):
                for part in event['content']['parts']:
                    if part.get('text'):
                        # Store each response chunk separately
                        response_chunks.append(part['text'])

        if not response_chunks:
            return https_fn.Response("Agent returned no response.", status=500, headers=headers)

        # The final report is the last item in the list
        full_response_text = response_chunks[-1]
        
        print("--- Agent's Final Response Chunk ---")
        print(full_response_text)
        print("------------------------------------")

        if full_response_text.strip().startswith("```json"):
            full_response_text = full_response_text[full_response_text.find('{'):full_response_text.rfind('}')+1]

        try:
            analysis_data = json.loads(full_response_text)
        except json.JSONDecodeError as e:
            error_message = f"Failed to decode the final JSON chunk from the agent. Error: {e}. Raw final chunk: '{full_response_text}'"
            return https_fn.Response(error_message, status=500, headers=headers)

        pdf_bytes = generate_pdf_from_json(analysis_data)
        bucket = storage.bucket()
        blob = bucket.blob(f"investment_memos/{analysis_id}.pdf")
        blob.upload_from_string(pdf_bytes, content_type='application/pdf')
        blob.make_public()
        generated_pdf_url = blob.public_url

        bigquery_client = bigquery.Client(project=PROJECT_ID)
        table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"

        # The agent sometimes returns the memo directly, and sometimes nested under 'investment_memo'.
        # This handles both cases by defaulting to the entire 'analysis_data' object if the key is missing.
        memo_data = analysis_data.get("investment_memo", analysis_data)
        if not memo_data:
            raise Exception("Agent response was empty or did not contain the expected investment memo data.")
        
        # Check if follow-up questions are included in the response
        followup_questions = analysis_data.get("followup_questions")
        if followup_questions:
            print("Storing follow-up questions...")
            try:
                # Setup follow-up questions table if needed
                setup_followup_questions_table()
                
                # Store follow-up questions in BigQuery
                company_name = memo_data.get("company_name", "Unknown Company")
                overall_assessment = followup_questions.get("overall_assessment", "")
                priority_concerns = followup_questions.get("priority_concerns", [])
                current_time = datetime.utcnow()
                
                # Prepare rows for BigQuery insertion
                rows_to_insert = []
                
                # Process each question
                for i, question in enumerate(followup_questions.get("questions", [])):
                    question_id = f"{analysis_id}_q_{i+1}"
                    row_data = {
                        "analysis_id": analysis_id,
                        "company_name": company_name,
                        "question_id": question_id,
                        "question": question.get("question", ""),
                        "context": question.get("context", ""),
                        "category": question.get("category", ""),
                        "founder_response": None,
                        "response_date": None,
                        "additional_notes": None,
                        "status": "pending",
                        "overall_assessment": overall_assessment,
                        "priority_concerns": json.dumps(priority_concerns),
                        "created_date": current_time,
                        "last_updated": current_time
                    }
                    rows_to_insert.append(row_data)
                
                # Insert into BigQuery
                followup_table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}"
                errors = bigquery_client.insert_rows_json(followup_table_ref_str, rows_to_insert)
                if errors:
                    print(f"Warning: BigQuery insertion for follow-up questions failed: {errors}")
                else:
                    print(f"Stored {len(rows_to_insert)} follow-up questions for {company_name}")
                
            except Exception as e:
                print(f"Warning: Failed to store follow-up questions: {e}")
                # Continue with the main analysis even if follow-up questions storage fails

        # --- Map Agent Response to BigQuery Schema ---
        row_to_insert = {
            "analysis_id": analysis_id,
            "user_id": user_id, # Add user_id to insertion
            "generated_pdf_url": generated_pdf_url,
            "company_name": memo_data.get("company_name"),
            "tech_field": tech_field,
            "company_website": company_website,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author": "VentureAI Agent",
            "introduction": memo_data.get("summary"),
            "problem": memo_data.get("problem_definition"),
            "product_description": memo_data.get("solution_description"),
            "business_model": memo_data.get("business_model"), # Add business_model
            "market_competition": memo_data.get("competitive_advantage"),
        }

        # Flatten nested objects
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

        # Convert list/dict fields to JSON strings for BigQuery
        for key, value in row_to_insert.items():
            if isinstance(value, (list, dict)):
                row_to_insert[key] = json.dumps(value)

        errors = bigquery_client.insert_rows_json(table_ref_str, [row_to_insert])
        if errors:
            raise Exception(f"BigQuery insertion failed: {errors}")
        else:
            print("New row successfully added to BigQuery.")

        db = get_firestore_client()
        session_doc_ref = db.collection(SESSIONS_COLLECTION).document(session_id)
        session_doc_ref.update({
            "state.analysis_id": analysis_id,
            "state.generated_pdf_url": generated_pdf_url,
            "state.tech_field": tech_field,
            "state.company_website": company_website,
            "state.short_description": short_description,
            "state.pitch_deck_url": pdf_url
        })

        response_data = json.dumps({"message": "Analysis complete", "analysis_id": analysis_id, "generated_pdf_url": generated_pdf_url})
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def get_investor_dashboard_data(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to generate investment analysis, now with CORS support.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    """
    Fetches all rows from the BigQuery pitch deck analysis table for the investor dashboard.
    """
    try:
        print("Received request for investor dashboard data.")
        
        bigquery_client = bigquery.Client(project=PROJECT_ID)
        
        table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"
        
        query = f"SELECT * FROM `{table_ref_str}`"
        
        print(f"Executing query: {query}")
        query_job = bigquery_client.query(query)
        
        # Fetch all rows from the query job
        rows = [dict(row) for row in query_job]
        
        print(f"Successfully fetched {len(rows)} rows from BigQuery.")
        
        # Convert the list of dictionaries to a JSON string
        response_data = json.dumps(rows, default=str) # Use default=str to handle dates/times
        
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in get_investor_dashboard_data: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def get_followup_questions(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to retrieve follow-up questions by analysis ID or company name.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    
    try:
        request_json = req.get_json(silent=True) if req.method == "POST" else {}
        
        analysis_id = request_json.get('analysis_id') if request_json else req.args.get('analysis_id')
        company_name = request_json.get('company_name') if request_json else req.args.get('company_name')
        status_filter = request_json.get('status') if request_json else req.args.get('status')
        
        if not analysis_id and not company_name:
            return https_fn.Response("Error: Please provide either 'analysis_id' or 'company_name'.", status=400, headers=headers)
        
        bigquery_client = bigquery.Client(project=PROJECT_ID)
        followup_table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}"
        
        # Build query based on filters
        if analysis_id:
            query = f"SELECT * FROM `{followup_table_ref_str}` WHERE analysis_id = @analysis_id"
            query_params = [bigquery.ScalarQueryParameter("analysis_id", "STRING", analysis_id)]
        else:
            query = f"SELECT * FROM `{followup_table_ref_str}` WHERE company_name = @company_name"
            query_params = [bigquery.ScalarQueryParameter("company_name", "STRING", company_name)]
        
        if status_filter:
            query += " AND status = @status"
            query_params.append(bigquery.ScalarQueryParameter("status", "STRING", status_filter))
        
        query += " ORDER BY created_date DESC"
        
        print(f"Executing query: {query}")
        query_job = bigquery_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        
        # Fetch all rows from the query job
        rows = [dict(row) for row in query_job]
        
        if not rows:
            return https_fn.Response("Error: No questions found.", status=404, headers=headers)
        
        print(f"Successfully fetched {len(rows)} questions from BigQuery.")
        
        # Convert the list of dictionaries to a JSON string
        response_data = json.dumps(rows, default=str)
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in get_followup_questions: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def store_founder_response(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to store founder responses to follow-up questions.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    
    try:
        request_json = req.get_json(silent=True)
        required_fields = ['analysis_id', 'question_id', 'response']
        if not request_json or not all(field in request_json for field in required_fields):
            return https_fn.Response(f"Error: Please provide {', '.join(required_fields)}.", status=400, headers=headers)

        analysis_id = request_json['analysis_id']
        question_id = request_json['question_id']
        response = request_json['response']
        additional_notes = request_json.get('additional_notes', '')
        
        bigquery_client = bigquery.Client(project=PROJECT_ID)
        followup_table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_FOLLOWUP_QUESTIONS_TABLE_ID}"
        
        # First, check if the question exists and get its current status
        check_query = f"""
        SELECT status, founder_response 
        FROM `{followup_table_ref_str}` 
        WHERE analysis_id = @analysis_id AND question_id = @question_id
        """
        
        query_params = [
            bigquery.ScalarQueryParameter("analysis_id", "STRING", analysis_id),
            bigquery.ScalarQueryParameter("question_id", "STRING", question_id)
        ]
        
        query_job = bigquery_client.query(check_query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        rows = [dict(row) for row in query_job]
        
        if not rows:
            return https_fn.Response("Error: Question not found.", status=404, headers=headers)
        
        current_status = rows[0].get('status')
        current_response = rows[0].get('founder_response')
        
        # Check if already answered
        if current_status == "answered" or current_response is not None:
            return https_fn.Response("Error: This question has already been answered.", status=400, headers=headers)
        
        # Update the question with the founder response
        update_query = f"""
        UPDATE `{followup_table_ref_str}`
        SET 
            founder_response = @founder_response,
            response_date = @response_date,
            additional_notes = @additional_notes,
            status = 'answered',
            last_updated = @last_updated
        WHERE analysis_id = @analysis_id AND question_id = @question_id
        """
        
        current_time = datetime.utcnow()
        founder_response_json = json.dumps({
            "response": response,
            "response_date": current_time.isoformat(),
            "additional_notes": additional_notes
        })
        
        update_params = [
            bigquery.ScalarQueryParameter("founder_response", "STRING", founder_response_json),
            bigquery.ScalarQueryParameter("response_date", "TIMESTAMP", current_time),
            bigquery.ScalarQueryParameter("additional_notes", "STRING", additional_notes),
            bigquery.ScalarQueryParameter("last_updated", "TIMESTAMP", current_time),
            bigquery.ScalarQueryParameter("analysis_id", "STRING", analysis_id),
            bigquery.ScalarQueryParameter("question_id", "STRING", question_id)
        ]
        
        update_job = bigquery_client.query(update_query, job_config=bigquery.QueryJobConfig(query_parameters=update_params))
        update_job.result()  # Wait for the job to complete
        
        print(f"Stored founder response for question {question_id} in analysis {analysis_id}")
        
        response_data = json.dumps({
            "success": True,
            "message": "Founder response stored successfully",
            "question_id": question_id,
            "status": "answered"
        })
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in store_founder_response: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)
