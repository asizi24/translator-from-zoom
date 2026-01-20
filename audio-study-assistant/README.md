# 🎧 Audio Study Assistant

A serverless application for processing audio lectures and generating Hebrew summaries with interactive quizzes using Google Cloud's Vertex AI (Gemini 1.5 Pro).

## Features

- **Audio Upload**: Upload audio files (MP3, WAV, M4A, FLAC, OGG, WebM)
- **Cloud Storage**: Files are stored in Google Cloud Storage
- **AI Analysis**: Uses Gemini 1.5 Pro to analyze audio content
- **Hebrew Summary**: Generates comprehensive lecture summaries in Hebrew
- **Interactive Quiz**: Creates 10-question multiple choice quizzes

## Tech Stack

- **Backend**: FastAPI (Python 3.10)
- **Frontend**: HTML/CSS/JavaScript
- **AI**: Vertex AI (Gemini 1.5 Pro)
- **Storage**: Google Cloud Storage
- **Deployment**: Google Cloud Run

## Setup

### 1. Configure Project Settings

Edit `main.py` and replace the placeholders:

```python
PROJECT_ID = "your-gcp-project-id"
BUCKET_NAME = "your-bucket-name"
```

### 2. Create GCS Bucket

```bash
gsutil mb -l us-central1 gs://your-bucket-name
```

### 3. Enable Required APIs

```bash
gcloud services enable \
    run.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com
```

### 4. Deploy to Cloud Run

```bash
# Build and deploy
gcloud run deploy audio-study-assistant \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 300
```

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up authentication
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# Run the server
uvicorn main:app --reload --port 8080
```

## API Endpoints

### `POST /upload`

Upload an audio file to GCS.

**Request**: `multipart/form-data` with `file` field

**Response**:

```json
{
    "gs_uri": "gs://bucket/audio-uploads/uuid_filename.mp3",
    "filename": "lecture.mp3",
    "message": "File uploaded successfully"
}
```

### `POST /analyze`

Analyze an audio file using Gemini.

**Request**:

```json
{
    "gs_uri": "gs://bucket/audio-uploads/uuid_filename.mp3"
}
```

**Response**:

```json
{
    "summary": "סיכום ההרצאה בעברית...",
    "quiz": [
        {
            "question": "שאלה?",
            "options": ["א. תשובה 1", "ב. תשובה 2", "ג. תשובה 3", "ד. תשובה 4"],
            "correct_answer": "א. תשובה 1",
            "explanation": "הסבר"
        }
    ],
    "raw_response": "..."
}
```

### `GET /health`

Health check endpoint.

## License

MIT
