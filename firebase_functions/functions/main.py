from firebase_functions import https_fn, firestore_fn
from firebase_functions.options import set_global_options, MemoryOption
from firebase_admin import initialize_app, firestore, storage, messaging
from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions
from google.api_core import exceptions

import os
import vertexai
from vertexai import agent_engines, generative_models
from vertexai.generative_models import Part, Content
import json
import requests
from datetime import datetime

# --- Configuration ---
# Best practice: Load configuration from environment variables with defaults.
PROJECT_ID = os.environ.get("PROJECT_ID", "valued-mediator-461216-k7")
LOCATION = os.environ.get("LOCATION", "us-central1")
DOCUMENT_AI_LOCATION = os.environ.get("DOCUMENT_AI_LOCATION", "us") # New variable for Document AI
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "2175876336764059648")
DATABASE = os.environ.get("DATABASE", "ventureai")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID", "6143611b8bf159c1")
MIME_TYPE = "application/pdf"
# --------------------

# Initialize Firebase Admin SDK once in the global scope.
initialize_app()
set_global_options(
    max_instances=10,
    memory=MemoryOption.GB_1,
    timeout_sec=300,  # Increase timeout to 5 minutes
)

# --- Lazy Initialization for Vertex AI Client ---
_remote_app = None
_db = None
_translate_client = None
_speech_client = None

def get_remote_app():
    """
    Initializes and returns the Vertex AI remote app, ensuring it's only
    created once per function instance.
    """
    global _remote_app
    if _remote_app is None:
        print("Initializing Vertex AI client for the first time...")
        engine_resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
        print(f"Connecting to Reasoning Engine: {engine_resource_name}")
        _remote_app = agent_engines.get(engine_resource_name)
        print("Vertex AI client initialized.")
    return _remote_app

@https_fn.on_request()
def create_session_VAI(req: https_fn.Request) -> https_fn.Response:
    """
    An HTTP endpoint that finds an existing session for a user_id,
    or creates a new one if none are found.
    Expects a JSON body with 'user_id' and an optional 'state' object.
    """
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'user_id' not in request_json:
            return https_fn.Response("Error: Please provide 'user_id' in the JSON body.", status=400)
        
        user_id = request_json['user_id']
        initial_state = request_json.get('state', {})

        # Get the initialized remote app
        remote_app = get_remote_app()

        # --- Find or Create a Session ---
        print(f"Checking for existing sessions for user '{user_id}'...")
        list_sessions_response = remote_app.list_sessions(user_id=user_id)
        
        session_id = None
        session_state = {}

        if list_sessions_response and list_sessions_response.get('sessions'):
            # Use the first existing session
            remote_session = list_sessions_response['sessions'][0]
            session_id = remote_session.get('id')
            session_state = remote_session.get('state', {})
            print(f"Found existing session with ID: {session_id}")
        else:
            # Or create a new one if none exist
            print(f"No existing sessions found for user '{user_id}'. Creating a new one.")
            new_session = remote_app.create_session(user_id=user_id, state=initial_state)
            session_id = new_session.get('id')
            session_state = new_session.get('state', {})
            print(f"Created new session with ID: {session_id}")
        
        if not session_id:
             raise Exception("Failed to get or create a session ID.")

        # Prepare the JSON response with both session ID and state
        response_data = json.dumps({
            "session_id": session_id,
            "state": session_state
        })
        
        return https_fn.Response(response_data, mimetype="application/json")

    except Exception as e:
        print(f"An internal error occurred: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500)

@https_fn.on_request()
def process_pdf_document(req: https_fn.Request) -> https_fn.Response:
    """
    An HTTP endpoint that processes a PDF from a URL using Document AI.
    Expects a JSON body with 'pdf_url'.
    """
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'pdf_url' not in request_json:
            return https_fn.Response("Error: Please provide 'pdf_url' in the JSON body.", status=400)

        pdf_url = request_json['pdf_url']

        if not PROJECT_ID or not PROCESSOR_ID:
            return https_fn.Response("Error: Server configuration missing project or processor ID.", status=500)

        # Download the PDF content from the URL
        response = requests.get(pdf_url)
        response.raise_for_status()
        image_content = response.content

        # Process the document with Document AI
        api_endpoint = f"{DOCUMENT_AI_LOCATION}-documentai.googleapis.com"
        print(f"Using Document AI API endpoint: {api_endpoint}")

        opts = ClientOptions(api_endpoint=api_endpoint)
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)
        full_processor_name = client.processor_path(PROJECT_ID, DOCUMENT_AI_LOCATION, PROCESSOR_ID)
        print(f"Using Document AI processor: {full_processor_name}")

        raw_document = documentai_v1.RawDocument(
            content=image_content,
            mime_type=MIME_TYPE,
        )

        request_doc_ai = documentai_v1.ProcessRequest(name=full_processor_name, raw_document=raw_document)
        result = client.process_document(request=request_doc_ai)
        document = result.document

        return https_fn.Response(document.text, mimetype="text/plain")

    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF from {pdf_url}: {e}")
        return https_fn.Response(f"Error: Could not download the PDF file. Details: {e}", status=400)
    except exceptions.GoogleAPICallError as e:
        print(f"Error calling Document AI API: {e}")
        return https_fn.Response(f"Error: Could not process the document. Details: {e}", status=500)
    except Exception as e:
        print(f"An internal error occurred: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500)
