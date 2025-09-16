import vertexai
from vertexai.preview import reasoning_engines
from vertexai import agent_engines
import os
from dotenv import load_dotenv
from google.auth import impersonated_credentials
from google.oauth2 import service_account
import google.auth

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")

initial_state = {
    "user_id": "venture_capitalist_123",
    "pitch_deck_url": "https://firebasestorage.googleapis.com/v0/b/valued-mediator-461216-k7.firebasestorage.app/o/BuildBlitz_Google_%20Agentic_AI_Day_Idea.pdf?alt=media&token=9fb96f1a-4ec3-4904-bc92-2f20175b6730"
}
USER_ID = "venture_capitalist_123"
PROMPT = "The permission is granted now analyse"

remote_app = vertexai.agent_engines.get(
    f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/2175876336764059648"
)
print(remote_app)

# Get existing sessions for the user
list_sessions_response = remote_app.list_sessions(user_id=USER_ID)
print(f"List sessions response: {list_sessions_response}")
sessions = list_sessions_response['sessions']
print(f"Found {len(sessions)} existing sessions.")
# sessions = list_sessions_response

if sessions:
    # Use the first existing session
    remote_session = sessions[0]
    print(f"Using existing session: {remote_session['id']}")
    print(f"Session state: {remote_session['state']}")
else:
    # Or create a new one if none exist
    print("No existing sessions found. Creating a new one.")
    remote_session = remote_app.create_session(user_id=USER_ID, state=initial_state)
    print(f"Created new session: {remote_session['id']}")
for event in remote_app.stream_query(
    user_id=USER_ID,
    session_id=remote_session["id"],
    message=PROMPT,
):
    print(event)