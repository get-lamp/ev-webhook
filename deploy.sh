#!/usr/bin/env bash
set -euo pipefail

# --- Configuration (matches terraform.tfvars) ---------------------------------
PROJECT="workshop-502013"
REGION="southamerica-east1"
SERVICE="webhook"
REPO="webhook"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

# --- Build --------------------------------------------------------------------
echo "=== Building Docker image ==="
docker build --platform linux/amd64 -t "$IMAGE" .

# --- Push ---------------------------------------------------------------------
echo "=== Pushing to Artifact Registry ==="
docker push "$IMAGE"

# --- Deploy -------------------------------------------------------------------
echo "=== Deploying to Cloud Run ==="
gcloud run deploy "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --image="$IMAGE" \
    --cpu=1 \
    --memory=256Mi \
    --timeout=60s \
    --min-instances=0 \
    --max-instances=10 \
    --allow-unauthenticated \
    --concurrency=80

echo "=== Done ==="
gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format="value(status.url)"
