from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1
import requests

# TODO(developer): Create a processor of type "OCR_PROCESSOR".

# TODO(developer): Update and uncomment these variables before running the sample.
project_id = "valued-mediator-461216-k7"

# Processor ID as hexadecimal characters.
# Not to be confused with the Processor Display Name.
processor_id = "6143611b8bf159c1"

# Processor location. For example: "us" or "eu".
location = "us"

# URL for the PDF file to process.
pdf_url = "https://firebasestorage.googleapis.com/v0/b/valued-mediator-461216-k7.firebasestorage.app/o/BuildBlitz_Google_%20Agentic_AI_Day_Idea.pdf?alt=media&token=9fb96f1a-4ec3-4904-bc92-2f20175b6730"

# Set `api_endpoint` if you use a location other than "us".
opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

# Initialize Document AI client.
client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)

# Get the Fully-qualified Processor path.
full_processor_name = client.processor_path(project_id, location, processor_id)

# Get a Processor reference.
request = documentai_v1.GetProcessorRequest(name=full_processor_name)
processor = client.get_processor(request=request)

# `processor.name` is the full resource name of the processor.
# For example: `projects/{project_id}/locations/{location}/processors/{processor_id}`
print(f"Processor Name: {processor.name}")

# Download the PDF content from the URL.
response = requests.get(pdf_url)
response.raise_for_status()  # Raise an exception for bad status codes
image_content = response.content

# Load binary data.
# For supported MIME types, refer to https://cloud.google.com/document-ai/docs/file-types
raw_document = documentai_v1.RawDocument(
    content=image_content,
    mime_type="application/pdf",
)

# Send a request and get the processed document.
request = documentai_v1.ProcessRequest(name=processor.name, raw_document=raw_document)
result = client.process_document(request=request)
document = result.document

# Read the text recognition output from the processor.
# For a full list of `Document` object attributes, reference this page:
# https://cloud.google.com/document-ai/docs/reference/rest/v1/Document
print("The document contains the following text:")
print(document.text)
