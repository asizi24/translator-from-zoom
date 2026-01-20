"""
Serverless Audio Study App - FastAPI Backend
Handles audio upload to GCS, Gemini analysis, and returns Hebrew summary + quiz.
"""
import os
import json
import shutil
import logging
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "zoom-audio-hybrid-store")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

# Initialize FastAPI
app = FastAPI(title="Audio Study Assistant", version="2.0.0")

# CORS - Allow all origins for Chrome Extension and local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize GCP clients
storage_client = None
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Vertex AI initialized: project={PROJECT_ID}, location={LOCATION}")
    storage_client = storage.Client()
    logger.info("GCS client initialized")
except Exception as e:
    logger.error(f"Failed to initialize GCP clients: {e}")


@app.get("/")
async def serve_frontend():
    """Serve the main frontend HTML"""
    return FileResponse("static/index.html")


@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    Main endpoint: Upload audio, analyze with Gemini, return summary and quiz.
    
    Flow:
    1. Stream upload to GCS (memory-safe for large files)
    2. Send to Gemini 1.5 Pro for analysis
    3. Delete audio from GCS (cost savings)
    4. Return JSON response
    """
    if not PROJECT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLOUD_PROJECT environment variable not set")
    
    if not storage_client:
        raise HTTPException(status_code=500, detail="GCS client not initialized")
    
    task_id = str(uuid.uuid4())
    audio_filename = f"uploads/{task_id}_{file.filename}"
    gcs_uri = f"gs://{BUCKET_NAME}/{audio_filename}"
    
    try:
        # Step 1: Stream upload to GCS (memory-safe)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(audio_filename)
        
        logger.info(f"Streaming upload to {gcs_uri}")
        
        # Use streaming write to avoid loading entire file into RAM
        with blob.open("wb") as gcs_file:
            shutil.copyfileobj(file.file, gcs_file, length=1024 * 1024)  # 1MB chunks
        
        logger.info(f"Upload complete: {gcs_uri}")
        
        # Step 2: Analyze with Gemini
        logger.info("Sending to Gemini 1.5 Pro...")
        model = GenerativeModel("gemini-1.5-pro")
        
        # Determine MIME type
        content_type = file.content_type or "audio/mpeg"
        audio_part = Part.from_uri(uri=gcs_uri, mime_type=content_type)
        
        prompt = """
אתה מורה פרטי מומחה. נתח את ההקלטה הזו וצור חומר לימודי בעברית.

החזר JSON בלבד (ללא markdown, ללא ```json) במבנה המדויק הבא:
{
    "summary": "סיכום מקיף של התוכן ב-3-4 פסקאות. כלול את הנושאים העיקריים והמסקנות.",
    "quiz": [
        {
            "question": "שאלה על החומר?",
            "options": ["תשובה א", "תשובה ב", "תשובה ג", "תשובה ד"],
            "correct_answer": "תשובה א",
            "explanation": "הסבר קצר למה זו התשובה הנכונה"
        }
    ]
}

חוקים:
1. הסיכום חייב להיות בעברית ומקיף
2. צור בדיוק 10 שאלות בחידון
3. כל שאלה חייבת 4 אפשרויות בדיוק
4. correct_answer חייב להיות זהה לאחת האפשרויות
5. החזר JSON תקין בלבד, ללא טקסט נוסף
"""
        
        response = model.generate_content(
            [audio_part, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        result_text = response.text
        logger.info("Gemini response received")
        
        # Parse JSON to validate format
        try:
            result_json = json.loads(result_text)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Gemini: {e}")
            # Return raw response if JSON parsing fails
            result_json = {"summary": result_text, "quiz": [], "raw_response": result_text}
        
        # Step 3: Cleanup - Delete audio file from GCS to save costs
        try:
            blob.delete()
            logger.info(f"Deleted {gcs_uri} from GCS")
        except Exception as e:
            logger.warning(f"Failed to delete {gcs_uri}: {e}")
        
        # Step 4: Return response
        return result_json
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        
        # Attempt cleanup on error
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(audio_filename)
            if blob.exists():
                blob.delete()
                logger.info(f"Cleaned up {gcs_uri} after error")
        except Exception:
            pass
        
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "project_id": PROJECT_ID,
        "bucket": BUCKET_NAME,
        "gcs_connected": storage_client is not None
    }


# Mount static files AFTER defining routes
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
