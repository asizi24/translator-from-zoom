# Deploy to Google Cloud Run
write-host "Starting Zoom AI Tutor Deployment..." -ForegroundColor Green

# 1. Configuration
$PROJECT_ID = Read-Host "Enter your Google Cloud Project ID"
$BUCKET_NAME = Read-Host "Enter your GCS Bucket Name"
$REGION = "us-central1"
$SERVICE_NAME = "zoom-translator"

# 2. Set Project
write-host "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# 3. Enable APIs (Just in case)
write-host "Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# 4. Deploy
write-host "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME `
  --source . `
  --platform managed `
  --region $REGION `
  --allow-unauthenticated `
  --port 8000 `
  --set-env-vars="BUCKET_NAME=$BUCKET_NAME,PROJECT_ID=$PROJECT_ID,LOCATION=$REGION"

write-host "Deployment Complete!" -ForegroundColor Green
write-host "Please ensure the Default Compute Service Account has 'Storage Object Admin' and 'Vertex AI User' roles."
