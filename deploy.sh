#!/bin/bash
# deploy.sh
# Deployment script for SupportPilot Admin Panel and Agent Runner Engine

set -e

# Automatically grab the current gcloud project
PROJECT_ID=$(gcloud config get-value project)
REGION="${REGION:-us-central1}"
ADMIN_SERVICE_NAME="${ADMIN_SERVICE_NAME:-supportpilot-admin}"
AGENT_IMAGE_NAME="gcr.io/$PROJECT_ID/${AGENT_IMAGE_NAME:-supportpilot-agent}:latest"

if [ -z "$PROJECT_ID" ]; then
    echo "⚠️ Warning: No Google Cloud project configured."
    echo "Please set it using: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "🚀 Starting Full Deployment Process for SupportPilot..."
echo "Target Project: $PROJECT_ID"
echo "Target Region: $REGION"

# -------------------------------------------------------------------
# 1. Build and Push the Agent Runner Image
# -------------------------------------------------------------------
echo ""
echo "--------------------------------------------------------"
echo "📦 Step 1: Building and pushing the Agent Runner image..."
echo "--------------------------------------------------------"
cd agent
gcloud builds submit --tag "$AGENT_IMAGE_NAME" --region="$REGION" --default-buckets-behavior=regional-user-owned-bucket .
cd ..

# -------------------------------------------------------------------
# 2. Deploy the Admin Panel
# -------------------------------------------------------------------
echo ""
echo "--------------------------------------------------------"
echo "🌐 Step 2: Deploying the Django Admin Panel..."
echo "--------------------------------------------------------"
gcloud run deploy "$ADMIN_SERVICE_NAME" \
  --source ./admin \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=$REGION" \
  --set-env-vars "BASE_AGENT_IMAGE=$AGENT_IMAGE_NAME" \
  --set-env-vars "DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-}" \
  --set-env-vars "FIRESTORE_DATABASE=${FIRESTORE_DATABASE:-}"

echo ""
echo "--------------------------------------------------------"
echo "✅ Deployment Complete!"
echo "You can access your Admin Panel at:"
gcloud run services describe "$ADMIN_SERVICE_NAME" --region "$REGION" --format 'value(status.url)'
echo "From the Admin Panel, you can now dynamically create and deploy new customer support agents!"
