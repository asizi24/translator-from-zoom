#!/bin/bash

# --- הגדרות ---
# Configuration
PROJECT_ID="gen-lang-client-0633910627"
BUCKET_NAME="zoom-audio-asaf-v1"
SERVICE_NAME="audio-study-app"
REGION="us-central1"

echo "🚀 Starting Deployment..."

# 1. הגדרת פרויקט
gcloud config set project $PROJECT_ID

# 2. הפעלת APIs
echo "🔌 Enabling APIs..."
gcloud services enable aiplatform.googleapis.com storage.googleapis.com run.googleapis.com

# 3. יצירת דלי (אם לא קיים)
echo "🪣 Checking Bucket..."
if ! gcloud storage buckets describe gs://$BUCKET_NAME > /dev/null 2>&1; then
  gcloud storage buckets create gs://$BUCKET_NAME --location=$REGION
  # מחיקת קבצים אוטומטית אחרי יום
  gcloud storage buckets update gs://$BUCKET_NAME --lifecycle-file=<(echo '{"rule":[{"action":{"type":"Delete"},"condition":{"age":1}}]}')
fi

# 4. פריסה ל-Cloud Run
echo "☁️ Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars BUCKET_NAME=$BUCKET_NAME \
  --memory 1Gi

echo "✅ Done! Service URL:"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
