from agent import root_agent
import vertexai
from vertexai.preview.reasoning_engines import AdkApp
from firestore.firestore_session_service import FirestoreSessionService
from google.adk.memory import VertexAiRagMemoryService
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
STAGING_BUCKET = os.getenv("STAGING_BUCKET")
DATABASE = os.getenv("DATABASE")

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)


def build_local_firestore_session_service():
    return FirestoreSessionService(project=PROJECT_ID, database=DATABASE)

def build_vertex_ai_rag_memory_service():
    return VertexAiRagMemoryService(
        rag_corpus="projects/valued-mediator-461216-k7/locations/us-central1/ragCorpora/6917529027641081856",
        similarity_top_k=5,
        vector_distance_threshold=0.7,
    )

# Pass the *builder function* to session_service_builder
adk_app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
    session_service_builder=build_local_firestore_session_service, # Pass the function, not an instance
    memory_service_builder=build_vertex_ai_rag_memory_service, # Pass the function, not an instance
)
