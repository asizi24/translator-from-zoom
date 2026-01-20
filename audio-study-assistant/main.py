"""
Audio Study Assistant - FastAPI Backend
Production-ready serverless application for Google Cloud Run
"""

import os
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage

import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Configuration
PROJECT_ID = "YOUR_PROJECT_ID"
BUCKET_NAME = "YOUR_BUCKET_NAME"
LOCATION = "us-central1"

# Initialize FastAPI
app = FastAPI(
    title="Audio Study Assistant",
    description="Upload audio lectures and get AI-powered summaries and quizzes",
    version="1.0.0"
)

# Configure CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (Chrome extension)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)


class AnalyzeRequest(BaseModel):
    """Request model for the analyze endpoint"""
    gs_uri: str


class AnalyzeResponse(BaseModel):
    """Response model for the analyze endpoint"""
    summary: str
    quiz: list | None = None
    raw_response: str


class UploadResponse(BaseModel):
    """Response model for the upload endpoint"""
    gs_uri: str
    filename: str
    message: str


def get_mime_type(filename: str) -> str:
    """Determine MIME type based on file extension"""
    extension = filename.lower().split('.')[-1]
    mime_types = {
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'flac': 'audio/flac',
        'm4a': 'audio/mp4',
        'ogg': 'audio/ogg',
        'webm': 'audio/webm',
        'aac': 'audio/aac',
        'wma': 'audio/x-ms-wma',
        'mp4': 'audio/mp4',
    }
    return mime_types.get(extension, 'audio/mpeg')


@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy", "service": "audio-study-assistant"}


@app.post("/upload", response_model=UploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file to Google Cloud Storage.
    
    Args:
        file: The audio file to upload
        
    Returns:
        UploadResponse with the GCS URI
    """
    try:
        # Validate file type
        allowed_extensions = {'mp3', 'wav', 'flac', 'm4a', 'ogg', 'webm', 'aac', 'wma', 'mp4'}
        file_extension = file.filename.lower().split('.')[-1] if file.filename else ''
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        
        # Initialize GCS client and upload
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"audio-uploads/{unique_filename}")
        
        # Read file content
        file_content = await file.read()
        
        # Upload to GCS
        blob.upload_from_string(
            file_content,
            content_type=get_mime_type(file.filename)
        )
        
        gs_uri = f"gs://{BUCKET_NAME}/audio-uploads/{unique_filename}"
        
        return UploadResponse(
            gs_uri=gs_uri,
            filename=file.filename,
            message="File uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_audio(request: AnalyzeRequest):
    """
    Analyze an audio file using Gemini 1.5 Pro.
    
    Args:
        request: AnalyzeRequest containing the GCS URI
        
    Returns:
        AnalyzeResponse with summary and quiz
    """
    try:
        # Validate GCS URI format
        if not request.gs_uri.startswith("gs://"):
            raise HTTPException(
                status_code=400,
                detail="Invalid GCS URI format. Must start with 'gs://'"
            )
        
        # Determine MIME type from URI
        filename = request.gs_uri.split('/')[-1]
        mime_type = get_mime_type(filename)
        
        # Initialize the model
        model = GenerativeModel("gemini-1.5-pro")
        
        # Create audio part from GCS URI
        audio_part = Part.from_uri(request.gs_uri, mime_type=mime_type)
        
        # Define the prompt
        prompt = """Summarize this lecture in Hebrew and create a 10-question multiple choice quiz in JSON format.

Your response should be in the following structure:
1. First, provide a comprehensive summary in Hebrew
2. Then, provide the quiz in valid JSON format with the following structure:

```json
{
  "quiz": [
    {
      "question": "השאלה בעברית",
      "options": ["א. תשובה 1", "ב. תשובה 2", "ג. תשובה 3", "ד. תשובה 4"],
      "correct_answer": "א. תשובה 1",
      "explanation": "הסבר קצר"
    }
  ]
}
```

Make sure the quiz tests understanding of key concepts from the lecture."""

        # Generate content
        response = model.generate_content([audio_part, prompt])
        
        raw_text = response.text
        
        # Try to extract quiz JSON from response
        quiz = None
        try:
            import json
            import re
            
            # Look for JSON block in response
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
            if json_match:
                quiz_data = json.loads(json_match.group(1))
                quiz = quiz_data.get('quiz', [])
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, quiz will remain None
            pass
        
        # Extract summary (text before JSON block)
        summary = raw_text
        if '```json' in raw_text:
            summary = raw_text.split('```json')[0].strip()
        
        return AnalyzeResponse(
            summary=summary,
            quiz=quiz,
            raw_response=raw_text
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze audio: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
