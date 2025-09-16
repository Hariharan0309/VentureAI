import logging
import requests
from google.adk.agents import Agent
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1
from google.api_core import exceptions
from google.adk.tools.tool_context import ToolContext

# Configuration for Document AI
PROJECT_ID = "valued-mediator-461216-k7"
PROCESSOR_ID = "6143611b8bf159c1"
LOCATION = "us"
MIME_TYPE = "application/pdf"


def get_document_text(tool_context: ToolContext) -> str:
    """
    Uses Document AI to extract text from a PDF.
    """
    logging.basicConfig(level=logging.INFO)
    session_state = tool_context.state
    pitch_deck_url = session_state.get("pitch_deck_url")

    if not pitch_deck_url:
        logging.error("pitch_deck_url not found in session state.")
        return "Error: pitch_deck_url not found in session state."

    try:
        # Download the PDF content from the URL
        response = requests.get(pitch_deck_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        image_content = response.content

        # Process the document with Document AI
        opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)

        full_processor_name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        raw_document = documentai_v1.RawDocument(
            content=image_content,
            mime_type=MIME_TYPE,
        )

        request = documentai_v1.ProcessRequest(name=full_processor_name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        return document.text

    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading PDF from {pitch_deck_url}: {e}")
        return f"Error: Could not download the PDF file. Details: {e}"
    except exceptions.GoogleAPICallError as e:
        logging.error(f"Error calling Document AI API: {e}")
        return f"Error: Could not process the document. Details: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return f"Error: An unexpected error occurred. Details: {e}"


pitch_analyzer_agent = Agent(
    name="pitch_analyzer",
    model="gemini-2.5-pro",
    description="A sub-agent that analyzes a pitch deck PDF to extract key points.",
    instruction="""
    You are a sub-agent specialized in analyzing pitch deck PDFs.
    You will be given the content of a PDF file.
    Your task is to use the get_document_text tool to extract the text from the PDF and then identify and return the key points.
    """,
    tools=[get_document_text],
)
