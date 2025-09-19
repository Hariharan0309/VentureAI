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

# Firestore Configuration
SESSIONS_COLLECTION = "adk_sessions"
# --------------------

# --- Initialization ---
initialize_app()
set_global_options(max_instances=10, memory=MemoryOption.GB_1, timeout_sec=540)

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
            bigquery.SchemaField("generated_pdf_url", "STRING"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("date", "STRING"),
            bigquery.SchemaField("author", "STRING"),
            bigquery.SchemaField("introduction", "STRING"),
            bigquery.SchemaField("opportunity", "STRING"),
            bigquery.SchemaField("key_strengths", "STRING"),
            bigquery.SchemaField("the_ask_summary", "STRING"),
            bigquery.SchemaField("recommendation", "STRING"),
            bigquery.SchemaField("justification", "STRING"),
            bigquery.SchemaField("product", "STRING"),
            bigquery.SchemaField("mission", "STRING"),
            bigquery.SchemaField("vision", "STRING"),
            bigquery.SchemaField("problem", "STRING"),
            bigquery.SchemaField("market_size_tam", "STRING"),
            bigquery.SchemaField("market_size_som", "STRING"),
            bigquery.SchemaField("market_validation", "STRING"),
            bigquery.SchemaField("product_description", "STRING"),
            bigquery.SchemaField("key_features", "STRING"),
            bigquery.SchemaField("impact_metrics", "STRING"),
            bigquery.SchemaField("founders", "STRING"),
            bigquery.SchemaField("team_strengths", "STRING"),
            bigquery.SchemaField("booked_customers", "STRING"),
            bigquery.SchemaField("pilots_running", "STRING"),
            bigquery.SchemaField("engagement_pipeline", "STRING"),
            bigquery.SchemaField("recognitions", "STRING"),
            bigquery.SchemaField("gtm_strategy", "STRING"),
            bigquery.SchemaField("ideal_customer_profile", "STRING"),
            bigquery.SchemaField("revenue_streams", "STRING"),
            bigquery.SchemaField("average_contract_value", "STRING"),
            bigquery.SchemaField("client_lifetime_value", "STRING"),
            bigquery.SchemaField("average_sales_cycle", "STRING"),
            bigquery.SchemaField("case_study_example", "STRING"),
            bigquery.SchemaField("fy_25_26_revenue", "STRING"),
            bigquery.SchemaField("growth_trajectory", "STRING"),
            bigquery.SchemaField("round_size", "STRING"),
            bigquery.SchemaField("round_type", "STRING"),
            bigquery.SchemaField("use_of_funds", "STRING"),
            bigquery.SchemaField("exit_strategy", "STRING"),
            bigquery.SchemaField("market_competition", "STRING"),
            bigquery.SchemaField("sales_cycle", "STRING"),
            bigquery.SchemaField("technical_risk", "STRING"),
            bigquery.SchemaField("model_scalability", "STRING"),
        ]
        table = bigquery.Table(table_ref_str, schema=schema)
        client.create_table(table)
        print(f"Table '{BIGQUERY_TABLE_ID}' created successfully.")

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
    """Finds or creates a user session."""
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'user_id' not in request_json:
            return https_fn.Response("Error: Please provide 'user_id' in the JSON body.", status=400)
        
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
        return https_fn.Response(response_data, mimetype="application/json")

    except Exception as e:
        print(f"An error occurred in create_session: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500)

@https_fn.on_request()
def generate_investment_analysis(req: https_fn.Request) -> https_fn.Response:
    global _bigquery_table_checked
    try:
        if not _bigquery_table_checked:
            setup_bigquery_table()
            _bigquery_table_checked = True

        request_json = req.get_json(silent=True)
        required_fields = ['user_id', 'session_id', 'pdf_url']
        if not request_json or not all(field in request_json for field in required_fields):
                return https_fn.Response(f"Error: Please provide {', '.join(required_fields)}.", status=400)

        user_id = request_json['user_id']
        session_id = request_json['session_id']
        pdf_url = request_json['pdf_url']
        prompt = request_json.get('prompt', "Analyze this pitch deck and return a comprehensive investment memo based on your defined output schema.")

        analysis_id = str(uuid.uuid4())
        remote_app = get_remote_app()
        
        response = requests.get(pdf_url)
        response.raise_for_status()
        pdf_data = response.content
        
        message_parts = [Part.from_data(data=pdf_data, mime_type="application/pdf"), Part.from_text(prompt)]
        final_message = Content(parts=message_parts, role="user").to_dict()

        print(f"Streaming query to manager_agent for session '{session_id}'...")
        full_response_text = ""
        for event in remote_app.stream_query(user_id=user_id, session_id=session_id, message=final_message):
            if event.get('content') and event.get('content').get('parts'):
                for part in event['content']['parts']:
                    if part.get('text'):
                        full_response_text += part['text']
        
        print("--- Agent's Raw Response ---")
        print(full_response_text)
        print("----------------------------")

        if full_response_text.strip().startswith("```json"):
            full_response_text = full_response_text[full_response_text.find('{'):full_response_text.rfind('}')+1]

        try:
            analysis_data = json.loads(full_response_text)
        except json.JSONDecodeError as e:
            error_message = f"The agent returned a response that was not valid JSON. Raw response: '{full_response_text}'"
            return https_fn.Response(error_message, status=500)

        pdf_bytes = generate_pdf_from_json(analysis_data)
        bucket = storage.bucket()
        blob = bucket.blob(f"investment_memos/{analysis_id}.pdf")
        blob.upload_from_string(pdf_bytes, content_type='application/pdf')
        blob.make_public()
        generated_pdf_url = blob.public_url

        bigquery_client = bigquery.Client(project=PROJECT_ID)
        table_ref_str = f"{PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"

        memo_data = analysis_data.get("investment_memo", {})
        if not memo_data:
            raise Exception("Agent response did not contain the expected 'investment_memo' object.")

        row_to_insert = {
            "analysis_id": analysis_id,
            "generated_pdf_url": generated_pdf_url,
            "company_name": memo_data.get("company_name"),
            "date": memo_data.get("date"),
            "author": memo_data.get("author"),
        }

        # Flatten nested objects
        sections_to_flatten = [
            "executive_summary", "company_overview", "problem_and_market_opportunity",
            "solution_and_product", "team", "traction_and_gtm", "business_model",
            "financial_projections", "the_ask", "potential_risks"
        ]
        for section in sections_to_flatten:
            row_to_insert.update(memo_data.get(section, {}))

        # Handle doubly-nested objects manually
        if isinstance(row_to_insert.get('market_size'), dict):
            market_size_data = row_to_insert.pop('market_size')
            row_to_insert['market_size_tam'] = market_size_data.get('tam')
            row_to_insert['market_size_som'] = market_size_data.get('som')
        
        if isinstance(row_to_insert.get('key_metrics'), dict):
            key_metrics_data = row_to_insert.pop('key_metrics')
            row_to_insert.update(key_metrics_data)

        # Rename conflicting key 'the_ask' from summary
        if 'the_ask' in row_to_insert:
            row_to_insert['the_ask_summary'] = row_to_insert.pop('the_ask')

        # Convert any remaining list/dict fields to JSON strings
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
            "state.generated_pdf_url": generated_pdf_url
        })

        response_data = json.dumps({"message": "Analysis complete", "analysis_id": analysis_id, "generated_pdf_url": generated_pdf_url})
        return https_fn.Response(response_data, mimetype="application/json")

    except Exception as e:
        print(f"An error occurred: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500)