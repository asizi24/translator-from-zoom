import os
import logging
import subprocess
import tempfile
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from dotenv import load_dotenv

# Optimization: increasing chunk size to 5MB for better stability
storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024

# Load env variables locally
load_dotenv()

# Configuration
# Configuration
from logging.handlers import RotatingFileHandler

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')

# Create formatters and add it to handlers
c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
if not logger.handlers:
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
# Trigger reload for key.json
LOCATION = os.getenv("LOCATION", "us-central1")

# Initialize Vertex AI
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-2.0-flash")
        logger.info(f"Vertex AI initialized: project={PROJECT_ID}")
    else:
        logger.warning("PROJECT_ID not set. Vertex AI not initialized.")
        model = None
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    model = None

app = FastAPI()

# Enable CORS for Chrome Extension & Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Frontend
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


class UrlRequest(BaseModel):
    url: str


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


def upload_to_gcs_and_analyze(audio_path: str, filename: str) -> dict:
    """Upload audio file to GCS and analyze with Gemini."""
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="BUCKET_NAME not set")
    if not model:
        raise HTTPException(status_code=500, detail="Vertex AI not initialized")

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    
    logger.info(f"Uploading {filename} to GCS")
    blob.upload_from_filename(audio_path, timeout=600)
    gs_uri = f"gs://{BUCKET_NAME}/{filename}"
    logger.info(f"Upload complete: {gs_uri}")
    
    try:
        logger.info("Sending to Gemini...")
        audio_part = Part.from_uri(uri=gs_uri, mime_type="audio/mpeg")
        
        prompt = """
        Analyze this audio file (Hebrew).
        1. Summarize the key points.
        2. Create a 10-question multiple choice quiz.
        Return RAW JSON.
        """
        
        response = model.generate_content([audio_part, prompt])
        logger.info("Gemini response received")
        
        # Cleanup GCS
        try:
            blob.delete()
            logger.info(f"Deleted {filename} from GCS")
        except Exception as e:
            logger.warning(f"Failed to delete blob: {e}")
        
        return {"result": response.text}
        
    except Exception as e:
        try:
            blob.delete()
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
def analyze_audio(file: UploadFile = File(...)):
    """Analyze uploaded audio file."""
    if not BUCKET_NAME or not model:
        raise HTTPException(status_code=500, detail="Service not configured")

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file.filename)
    
    logger.info(f"Starting upload for {file.filename}")
    blob.upload_from_file(file.file, timeout=600)
    gs_uri = f"gs://{BUCKET_NAME}/{file.filename}"
    logger.info(f"Upload complete: {gs_uri}")
    
    try:
        logger.info("Sending to Gemini...")
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
        
        try:
            blob.delete()
            logger.info(f"Deleted {file.filename} from GCS")
        except Exception as e:
            logger.warning(f"Failed to delete blob: {e}")
        
        return {"result": response.text}
        
    except Exception as e:
        try:
            blob.delete()
        except:
            pass
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-url")
async def analyze_url(request: UrlRequest):
    """Download video from URL, extract audio, and analyze with Gemini."""
    url = request.url
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    task_id = str(uuid.uuid4())[:8]  # Short ID for safe filenames
    
    # Use system temp to avoid Hebrew path issues on Windows
    safe_temp = os.environ.get("TEMP", "/tmp")
    audio_filename = f"audio_{task_id}.mp3"
    audio_path = os.path.join(safe_temp, audio_filename)
    
    try:
        # Step 1: Download and extract audio directly with yt-dlp
        # Using -x (extract audio) + --audio-format mp3 to skip ffmpeg step
        logger.info(f"Downloading audio from: {url}")
        download_cmd = [
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", "mp3",
            "--audio-quality", "4",
            "-o", audio_path.replace(".mp3", ".%(ext)s"),  # yt-dlp will add extension
            "--no-playlist",
            "--no-warnings",
            "--quiet",
            url
        ]
        
        result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            error_msg = result.stderr or "Unknown download error"
            logger.error(f"yt-dlp error: {error_msg}")
            raise HTTPException(status_code=400, detail=f"הורדה נכשלה: {error_msg[:200]}")
        
        # Find the downloaded mp3 file
        if not os.path.exists(audio_path):
            # yt-dlp might have created it with different name
            possible_files = [f for f in os.listdir(safe_temp) if f.startswith(f"audio_{task_id}") and f.endswith(".mp3")]
            if possible_files:
                audio_path = os.path.join(safe_temp, possible_files[0])
            else:
                raise HTTPException(status_code=500, detail="הורדה נכשלה - קובץ לא נמצא")
        
        logger.info(f"Audio downloaded: {audio_path}")
        
        # Step 2: Upload to GCS and analyze
        result = upload_to_gcs_and_analyze(audio_path, audio_filename)
        
        # Cleanup local file
        try:
            os.remove(audio_path)
        except:
            pass
        
        return result
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="זמן ההורדה פג - נסה קובץ קטן יותר")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        # Cleanup on error
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))
