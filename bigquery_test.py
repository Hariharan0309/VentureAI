from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import uuid

# --- Configuration ---
# Replace with your project ID.
PROJECT_ID = "valued-mediator-461216-k7"
# This is the dataset and table the script will create and use.
DATASET_ID = "venture_ai_test_dataset"
TABLE_ID = "pitch_deck_analysis_v2"
# --------------------

def run_bigquery_test():
    """
    A simple script to demonstrate creating a table, inserting data,
    and querying data in Google BigQuery.
    """
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    # --- 1. Setup: Create Dataset and Table ---
    try:
        dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
        try:
            client.get_dataset(dataset_ref)
            print(f"Dataset '{DATASET_ID}' already exists.")
        except NotFound:
            print(f"Dataset '{DATASET_ID}' not found, creating it...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            client.create_dataset(dataset, timeout=30)
            print(f"Dataset '{DATASET_ID}' created.")

        try:
            client.get_table(table_ref)
            print(f"Table '{TABLE_ID}' already exists.")
        except NotFound:
            print(f"Table '{TABLE_ID}' not found, creating it...")
            schema = [
                bigquery.SchemaField("analysis_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("company_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("industry_sector", "STRING"),  # Added industry sector
                bigquery.SchemaField("summary_text", "STRING"),
                bigquery.SchemaField("funding_amount_requested", "INTEGER"),
            ]
            table = bigquery.Table(table_ref, schema=schema)
            client.create_table(table)
            print(f"Table '{TABLE_ID}' created.")

    except Exception as e:
        print(f"An error occurred during setup: {e}")
        return

    # --- 2. Insert Data ---
    rows_to_insert = [
        {
            "analysis_id": str(uuid.uuid4()),
            "company_name": "Innovate Inc.",
            "industry_sector": "Fintech",
            "summary_text": "A revolutionary new platform for AI-driven development.",
            "funding_amount_requested": 5000000,
        },
        {
            "analysis_id": str(uuid.uuid4()),
            "company_name": "GreenFields Tech",
            "industry_sector": "Agriculture",
            "summary_text": "Using drones and AI for precision farming.",
            "funding_amount_requested": 1500000,
        },
    ]

    print(f"\nInserting {len(rows_to_insert)} rows into '{TABLE_ID}'...")
    # For this example, we clear the table before inserting to avoid duplicates on re-runs.
    # In a real application, you would likely not do this.
    client.query(f"TRUNCATE TABLE `{table_ref}`").result()
    errors = client.insert_rows_json(table_ref, rows_to_insert)
    if not errors:
        print("New rows have been added successfully.")
    else:
        print(f"Encountered errors while inserting rows: {errors}")
        return

    # --- 3. Query and Display All Data ---
    print(f"\nQuerying all data from '{TABLE_ID}':")
    query_all = f"SELECT * FROM `{table_ref}`"
    try:
        query_job_all = client.query(query_all)
        print("Query successful. Results:")
        for row in query_job_all:
            print(f"- Company: {row['company_name']}, Industry: {row['industry_sector']}")
    except Exception as e:
        print(f"An error occurred during query: {e}")

    # --- 4. Query with a WHERE clause ---
    print(f"\nQuerying for 'Agriculture' startups:")
    query_filtered = f"""
        SELECT company_name, funding_amount_requested
        FROM `{table_ref}`
        WHERE industry_sector = 'Agriculture'
    """
    try:
        query_job_filtered = client.query(query_filtered)
        print("Query successful. Results:")
        results_filtered = list(query_job_filtered)
        if not results_filtered:
            print("No startups found for the 'Agriculture' sector.")
        else:
            for row in results_filtered:
                print(f"- Company: {row.company_name}, Funding: ${row.funding_amount_requested:,}")
    except Exception as e:
        print(f"An error occurred during filtered query: {e}")

if __name__ == "__main__":
    print("--- BigQuery Python Test Script ---")
    run_bigquery_test()
    print("\n--- Script Finished ---")