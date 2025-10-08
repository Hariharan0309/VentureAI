# VentureAI

VentureAI is an AI-powered platform that transforms messy founder materials and public data into concise, actionable investment insights. Cut through the noise and make smarter, faster investment decisions with automated due diligence.

## Introduction

VentureAI is designed to streamline the due diligence process for venture capitalists and provide founders with valuable insights. It automates the analysis of pitch decks, enriches information with web research, generates structured investment memos, answers investor queries, and even formulates challenging follow-up questions for founders. By leveraging Google Cloud's AI and data services, VentureAI aims to democratize data analysis and accelerate investment decision-making.

## Features

* **Pitch Deck Analysis:** Automatically extracts key claims and data from PDF pitch decks, covering aspects like team, problem, solution, market size, traction, business model, competitors, and funding ask.
* **Web Research & Verification:** Utilizes Google Search to independently verify claims made in pitch decks and gather additional public information on market size, competitors, founder backgrounds, and company traction.
* **Structured Investment Memo Generation:** Synthesizes extracted pitch deck data and web research findings into a comprehensive, structured investment memo, highlighting discrepancies and providing a clear investment recommendation.
* **Investor Query Answering:** Allows investors to ask natural language questions about specific investment analyses, retrieving relevant data from BigQuery to provide informed answers.
* **Follow-up Question Generation:** Generates challenging and insightful follow-up questions for founders, designed to clarify discrepancies, address concerns, and validate key assumptions during due diligence.
* **BigQuery Integration:** Stores all investment analysis data in Google BigQuery, enabling robust data warehousing and dashboarding for investors.
* **Firebase Integration:**
  * **Firebase Cloud Functions:** Provides HTTP endpoints for initiating pitch deck analysis, querying the agent, and generating follow-up questions.
    * **Firestore:** Manages user sessions and stores session-specific state.
    * **Firebase Storage:** Stores generated PDF investment memos, making them accessible via public URLs.
* **LinkedIn Scraping:** Includes a utility for scraping LinkedIn profiles to gather founder background information (used for data collection).

## Architecture

VentureAI is built on a robust, serverless architecture leveraging Google Cloud Platform services:

* **Vertex AI Agent:** The core intelligence of VentureAI is a Vertex AI Agent (built with the Agent Development Kit - ADK) that orchestrates the entire analysis workflow. This agent comprises several specialized sub-agents:
  * `pitch_deck_extractor_agent`: Extracts raw data from pitch decks.
  * `web_research_analyst_agent`: Performs external research using Google Search.
  * `report_generation_agent`: Synthesizes information into a structured investment memo.
  * `investor_query_agent`: Answers specific questions based on stored analysis.
  * `followup_questions_agent`: Generates due diligence questions.
* **Firebase Cloud Functions:** Act as the API layer, exposing HTTP endpoints that trigger the Vertex AI Agent and interact with other Google Cloud services.
* **Google Cloud Document AI:** Used by the `process_document.py` utility to extract text from PDF pitch decks.
* **Google BigQuery:** The primary data warehouse for storing all generated investment analysis reports and related metadata.
* **Google Cloud Firestore:** Used for managing and persisting user session states for the Vertex AI Agent.
* **Firebase Storage:** Stores the generated PDF investment memos.
* **Scrapy:** A Python framework used for web scraping, specifically for LinkedIn profiles.

## Setup and Deployment

### Prerequisites

* Google Cloud Project with billing enabled.
* `gcloud` CLI installed and configured.
* Python 3.9+
* `npm` (for Firebase CLI)
* Firebase CLI installed (`npm install -g firebase-tools`)

### Environment Configuration

Create a `.env` file in the root directory and in `firebase_functions/functions/` with the following variables:

```bash
PROJECT="your-gcp-project-id"
REGION="us-central1" # Or your preferred region
STAGING_BUCKET="gs://your-vertex-ai-staging-bucket"
CUSTOM_SA_EMAIL="your-vertex-ai-service-account@your-gcp-project-id.iam.gserviceaccount.com"
DATABASE="(default)" # For Firestore
REASONING_ENGINE_ID="your-reasoning-engine-id" # After first deployment
BIGQUERY_DATASET_ID="venture_ai_test_dataset"
BIGQUERY_TABLE_ID="pitch_deck_analysis"
```

### Deployment Steps

1. **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    pip install -r firebase_functions/functions/requirements.txt
    ```

2. **Deploy Vertex AI Agent:**
    Navigate to the project root and run the `deploy.py` script. This will create or update the Vertex AI Reasoning Engine.

    ```bash
    python deploy.py
    ```

    *Note: The first deployment will create the Reasoning Engine and provide its ID. Update `REASONING_ENGINE_ID` in your `.env` files with this ID.*
3. **Deploy Firebase Cloud Functions:**
    Navigate to the `firebase_functions` directory and deploy the functions.

    ```bash
    cd firebase_functions
    firebase deploy --only functions
    ```

## Usage

Once deployed, you can interact with VentureAI via the Firebase Cloud Function HTTP endpoints:

* **`create_session`:**
  * **Method:** `POST`
  * **URL:** `https://<REGION>-<PROJECT_ID>.cloudfunctions.net/create_session`
  * **Body:** `{"user_id": "your_user_id", "state": {}}`
  * **Description:** Creates or retrieves a user session for interaction with the agent.
* **`generate_investment_analysis`:**
  * **Method:** `POST`
  * **URL:** `https://<REGION>-<PROJECT_ID>.cloudfunctions.net/generate_investment_analysis`
  * **Body:** `{"user_id": "your_user_id", "session_id": "your_session_id", "pdf_url": "url_to_pitch_deck.pdf", "tech_field": "Fintech", "short_description": "A brief description of the company"}`
  * **Description:** Initiates the full pitch deck analysis workflow, generating an investment memo and storing it.
* **`get_investor_dashboard_data`:**
  * **Method:** `GET`
  * **URL:** `https://<REGION>-<PROJECT_ID>.cloudfunctions.net/get_investor_dashboard_data`
  * **Description:** Retrieves all stored investment analysis data for dashboarding purposes.
* **`invester_query_agent_function`:**
  * **Method:** `POST`
  * **URL:** `https://<REGION>-<PROJECT_ID>.cloudfunctions.net/invester_query_agent_function`
  * **Body:** `{"user_id": "your_user_id", "session_id": "your_session_id", "prompt": "What is the market size?", "analysis_id": "the_analysis_id_to_query"}`
  * **Description:** Allows investors to ask questions about a specific analysis.
* **`followup_question`:**
  * **Method:** `POST`
  * **URL:** `https://<REGION>-<PROJECT_ID>.cloudfunctions.net/followup_question`
  * **Body:** `{"user_id": "your_user_id", "session_id": "your_session_id"}`
  * **Description:** Generates follow-up questions for the founder based on the current session's analysis.

## Technologies Used

* **Google Cloud Platform:**
  * Vertex AI (Agent Builder, Reasoning Engine)
  * Firebase (Cloud Functions, Firestore, Storage)
  * BigQuery
  * Document AI
* **Python:**
  * `google-cloud-aiplatform[adk,agent_engines]`
  * `google-cloud-firestore`
  * `google-cloud-bigquery`
  * `google-cloud-documentai`
  * `requests`
  * `python-dotenv`
  * `scrapy`
  * `pydantic`
  * `reportlab`
  * `fpdf2`
  * `firebase-admin`
* **Other:**
  * `dotenv`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
