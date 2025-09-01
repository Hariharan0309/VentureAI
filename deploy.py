from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

import click
import google.auth
from google.auth import impersonated_credentials
from google.oauth2 import service_account
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
temp_folder = 'tmp'
agent_folder = 'manager_agent'
tool_folder = 'tools'
adk_app = 'adk_app'
requirements_file = 'requirements.txt'
project = os.getenv('PROJECT')
region = os.getenv('REGION')
staging_bucket = os.getenv('STAGING_BUCKET')
display_name = 'VentureAI'
description = 'An agent for venture capitalists and startup founders.'
CUSTOM_SA_EMAIL = os.getenv('CUSTOM_SA_EMAIL')


def _resolve_project(project_in_option: Optional[str]) -> str:
  """Gets the project ID from gcloud config if not provided."""
  if project_in_option:
    return project_in_option
  result = subprocess.run(
      ['gcloud', 'config', 'get-value', 'project'],
      check=True,
      capture_output=True,
      text=True,
  )
  project = result.stdout.strip()
  click.echo(f'Use default project: {project}')
  return project

def find_agent_by_display_name(display_name_to_find: str) -> Optional[agent_engines.AgentEngine]:
    """Finds an existing Reasoning Engine by its display name."""
    click.echo(f"Searching for an existing agent with display name: '{display_name_to_find}'...")
    all_agents = agent_engines.list()
    for agent in all_agents:
        if agent.display_name == display_name_to_find:
            click.echo(f"Found existing agent: {agent.resource_name}")
            return agent
    click.echo("No existing agent found with that display name.")
    return None

# --- Main Script ---

if os.path.exists(temp_folder):
    click.echo('Removing existing temp folder...')
    shutil.rmtree(temp_folder)

try:
    click.echo('Copying agent source code...')
    # Copy the entire agent folder to the temp directory.
    # This assumes adk_app.py and all other necessary files are inside this folder.
    shutil.copytree(agent_folder, temp_folder, dirs_exist_ok=True)
    click.echo('Copying agent source code complete.')

    click.echo('Initializing Vertex AI...')
    import sys
    sys.path.append(temp_folder)
    project = _resolve_project(project)

    # --- Impersonation Credentials Setup ---
    source_credentials, _ = google.auth.default()
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=CUSTOM_SA_EMAIL,
        target_scopes=['https://www.googleapis.com/auth/cloud-platform']
    )

    vertexai.init(
        project=project,
        location=region,
        staging_bucket=staging_bucket,
        credentials=target_credentials 
    )
    click.echo('Vertex AI initialized.')

    # --- Construct the Agent Object ---
    # This object defines the code and entry points for the agent.
    agent_to_deploy = agent_engines.ModuleAgent(
        module_name=adk_app,
        agent_name='adk_app',
        register_operations={
            '': [
                'get_session',
                'list_sessions',
                'create_session',
                'delete_session',
            ],
            'async': [
                'async_get_session',
                'async_list_sessions',
                'async_create_session',
                'async_delete_session',
            ],
            'async_stream': ['async_stream_query'],
            'stream': ['stream_query', 'streaming_agent_run_with_events'],
        },
       sys_paths=[temp_folder],
    )

    # --- Find or Create/Update Logic ---
    existing_agent = find_agent_by_display_name(display_name)
    
    requirements_path = os.path.join(temp_folder, requirements_file)
    # Ensure a requirements file exists with necessary packages.
    if not os.path.exists(requirements_path):
        with open(requirements_path, 'w', encoding='utf-8') as f:
            f.write('google-cloud-aiplatform[adk,agent_engines]\n')
            f.write('google-cloud-firestore\n')
            f.write('python-dotenv\n')

    # Read environment variables if an .env file exists in the source folder
    env_vars = None
    env_file_path = os.path.join(temp_folder, '.env')
    if os.path.exists(env_file_path):
        from dotenv import dotenv_values
        click.echo(f'Reading environment variables from {env_file_path}')
        env_vars = dotenv_values(env_file_path)


    if existing_agent:
        # If an agent exists, update it in-place.
        click.echo('Updating existing agent engine...')
        existing_agent.update(
            agent_engine=agent_to_deploy,
            requirements=requirements_path,
            description=description,
            env_vars=env_vars,
            extra_packages=[temp_folder]
        )
        click.echo(f"Agent '{display_name}' updated successfully.")
    else:
        # If no agent exists, create a new one.
        click.echo('Creating new agent engine...')
        agent_engines.create(
            agent_engine=agent_to_deploy,
            requirements=requirements_path,
            display_name=display_name,
            description=description,
            env_vars=env_vars,
            extra_packages=[temp_folder]
        )
        click.echo(f"New agent '{display_name}' created successfully.")

finally:
    click.echo(f'Cleaning up the temp folder: {temp_folder}')
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
