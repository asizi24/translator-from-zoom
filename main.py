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
    blob.upload_from_filename(audio_path)
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
async def analyze_audio(file: UploadFile = File(...)):
    """Analyze uploaded audio file."""
    if not BUCKET_NAME or not model:
        raise HTTPException(status_code=500, detail="Service not configured")

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file.filename)
    
    logger.info(f"Starting upload for {file.filename}")
    blob.upload_from_file(file.file)
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
    
    task_id = str(uuid.uuid4())
    
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, f"{task_id}_video")
        audio_path = os.path.join(temp_dir, f"{task_id}.mp3")
        
        try:
            # Step 1: Download video with yt-dlp
            logger.info(f"Downloading video from: {url}")
            download_cmd = [
                "yt-dlp",
                "-f", "bestaudio/best",
                "-o", video_path,
                "--no-playlist",
                url
            ]
            result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                logger.error(f"yt-dlp error: {result.stderr}")
                raise HTTPException(status_code=400, detail=f"Failed to download video: {result.stderr}")
            
            # Find the downloaded file (yt-dlp adds extension)
            downloaded_files = [f for f in os.listdir(temp_dir) if f.startswith(task_id) and not f.endswith('.mp3')]
            if not downloaded_files:
                raise HTTPException(status_code=500, detail="Download failed - no file found")
            
            actual_video_path = os.path.join(temp_dir, downloaded_files[0])
            logger.info(f"Downloaded: {actual_video_path}")
            
            # Step 2: Extract audio with ffmpeg
            logger.info("Extracting audio with ffmpeg...")
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", actual_video_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-q:a", "4",
                "-y",
                audio_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0 or not os.path.exists(audio_path):
                logger.error(f"ffmpeg error: {result.stderr}")
                raise HTTPException(status_code=500, detail="Failed to extract audio")
            
            logger.info(f"Audio extracted: {audio_path}")
            
            # Step 3: Upload to GCS and analyze
            return upload_to_gcs_and_analyze(audio_path, f"{task_id}.mp3")
            
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Download/conversion timeout")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))
