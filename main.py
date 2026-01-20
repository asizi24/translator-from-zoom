import os
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
LOCATION = os.getenv("LOCATION", "us-central1")

# Initialize Vertex AI
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-1.5-pro-preview-0409")
        logger.info(f"Vertex AI initialized: project={PROJECT_ID}")
    else:
        logger.warning("PROJECT_ID not set. Vertex AI not initialized.")
        model = None
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    model = None

app = FastAPI()

# 1. FIX: Enable CORS for Chrome Extension & Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Frontend (Drag & Drop UI)
# We mount static first, but we also want / to serve index.html
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="BUCKET_NAME environment variable not set")
    
    if not model:
        raise HTTPException(status_code=500, detail="Vertex AI model not initialized")

    # 2. FIX: Direct Stream Upload to GCS (No RAM usage)
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file.filename)
        
        logger.info(f"Starting upload for {file.filename}")
        # This reads from the incoming stream and writes to GCS simultaneously
        blob.upload_from_file(file.file)
        logger.info(f"Upload completed for {file.filename}")
        
        gs_uri = f"gs://{BUCKET_NAME}/{file.filename}"
    except Exception as e:
        logger.error(f"Failed to upload to GCS: {e}")
        raise HTTPException(status_code=500, detail=f"GCS Upload Failed: {str(e)}")
    
    try:
        # 3. Call Gemini
        logger.info(f"Sending to Gemini: {gs_uri}")
        # Determine mime type based on extension or header, default to audio/mpeg
        mime_type = file.content_type or "audio/mpeg"
        audio_part = Part.from_uri(uri=gs_uri, mime_type=mime_type)
        
        prompt = """
        Analyze this audio file (Hebrew).
        1. Summarize the key points.
        2. Create a 10-question multiple choice quiz.
        Return RAW JSON.
        """
        
        response = model.generate_content([audio_part, prompt])
        logger.info("Gemini response received")
        
        # 4. FIX: Cleanup (Delete file to save money)
        try:
            blob.delete()
            logger.info(f"Deleted {file.filename} from GCS")
        except Exception as e:
            logger.warning(f"Failed to delete blob {file.filename}: {e}")
        
        return {"result": response.text}
        
    except Exception as e:
        # Try to cleanup even if error
        try: 
            blob.delete()
        except: 
            pass
        logger.error(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
