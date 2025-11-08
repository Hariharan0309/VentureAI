#!/bin/bash

# Exit on error
set -e

# --- Configuration ---
IMAGE_NAME="venture-ai"
GCP_PROJECT_ID="valued-mediator-461216-k7" # Replace with your GCP Project ID
GCP_REGION="us-central1" # Replace with your desired GCP region
ARTIFACT_REGISTRY_REPO="my-adk-repo" # Replace with your Artifact Registry repo name
CLOUD_RUN_SERVICE_NAME="venture-ai-service"

# --- Functions ---
build_image() {
  echo "--- Building Docker image: $IMAGE_NAME ---"
  docker build -t "$IMAGE_NAME" -f Dockerfile .
}

run_local() {
  echo "--- Running Docker container locally ---"
  echo "Stopping and removing existing container if it exists..."
  docker stop venture-ai-container >/dev/null 2>&1 || true
  docker rm venture-ai-container >/dev/null 2>&1 || true
  
  echo "Starting new container..."
  docker run -p 8080:8080 --name venture-ai-container \
    -v ~/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json \
    -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
    "$IMAGE_NAME"
  
  echo "--- Container running. Access at http://localhost:8080 ---"
}

deploy_to_cloud_run() {
  echo "--- Deploying to Cloud Run ---"
  
  # Tag the image for Artifact Registry
  ARTIFACT_REGISTRY_IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:latest"
  docker tag "$IMAGE_NAME" "$ARTIFACT_REGISTRY_IMAGE_TAG"
  
  # Push the image to Artifact Registry
  echo "--- Pushing image to Google Artifact Registry ---"
  gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
  docker push "$ARTIFACT_REGISTRY_IMAGE_TAG"
  
  # Deploy to Cloud Run
  echo "--- Deploying image to Cloud Run service: $CLOUD_RUN_SERVICE_NAME ---"
  gcloud run deploy "$CLOUD_RUN_SERVICE_NAME" \
    --image="$ARTIFACT_REGISTRY_IMAGE_TAG" \
    --platform=managed \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --allow-unauthenticated \
    --set-env-vars="GCS_BUCKET_NAME=valued-mediator-461216-k7.firebasestorage.app,PROJECT_ID=valued-mediator-461216-k7,LOCATION=us-central1,DATABASE=ventureai,GOOGLE_API_KEY=AIzaSyDLQ_sxIz7TUUdHnmcotLlXwBD_PyVyFOQ" \
    --quiet
    
  echo "--- Deployment complete ---"
}

# --- Main script ---
deploy=false
while getopts ":r" opt; do
  case ${opt} in
    r )
      deploy=true
      ;;
    \? )
      echo "Invalid option: -$OPTARG" 1>&2
      exit 1
      ;;
  esac
done


if [ "$deploy" = true ]; then
  deploy_to_cloud_run
else
  build_image
  run_local
fi
