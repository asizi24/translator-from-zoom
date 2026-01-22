import os
import logging
import subprocess
import tempfile
import uuid
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Logger Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Constants & Env Vars
PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
LOCATION = os.getenv("LOCATION", "us-central1")

# Initialize Vertex AI
model = None
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-2.0-flash")
        logger.info(f"Vertex AI initialized: project={PROJECT_ID}")
    else:
        logger.warning("PROJECT_ID not set. Vertex AI features will be disabled.")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")

# GCS Defaults
storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024  # 5MB chunks

# FastAPI App
app = FastAPI(title="Zoom AI Tutor")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
app.mount("/static", StaticFiles(directory="static", html=True), name="static")
templates = Jinja2Templates(directory="templates")

# Models
class UrlRequest(BaseModel):
    url: str

class AskRequest(BaseModel):
    task_id: str
    question: str

# --- GCS Helper Functions ---

def get_storage_client():
    try:
        return storage.Client()
    except Exception as e:
        logger.error(f"Failed to create storage client: {e}")
        return None

def save_task_status(task_id: str, status_data: Dict[str, Any]):
    """Saves task status to GCS as JSON."""
    if not BUCKET_NAME:
        logger.error("BUCKET_NAME not set, cannot save status")
        return

    client = get_storage_client()
    if not client: return

    try:
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"tasks/{task_id}/status.json")
        blob.upload_from_string(json.dumps(status_data), content_type="application/json")
    except Exception as e:
        logger.error(f"Error saving task status {task_id}: {e}")

def load_task_status(task_id: str) -> Dict[str, Any]:
    """Loads task status from GCS."""
    if not BUCKET_NAME: return {"error": "Server configuration error"}

    client = get_storage_client()
    if not client: return {"error": "GCP Credentials missing"}

    try:
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"tasks/{task_id}/status.json")
        if not blob.exists():
            return {"error": "Task not found"}
        
        data = json.loads(blob.download_as_text())
        return data
    except Exception as e:
        logger.error(f"Error loading task status {task_id}: {e}")
        return {"error": str(e)}

def save_result_to_gcs(task_id: str, result: str):
    """Saves the final transcript/analysis result."""
    if not BUCKET_NAME: return
    
    client = get_storage_client()
    if not client: return

    try:
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"tasks/{task_id}/result.json")
        blob.upload_from_string(json.dumps({"result": result}), content_type="application/json")
    except Exception as e:
        logger.error(f"Failed to save result for {task_id}: {e}")

def load_result_from_gcs(task_id: str) -> Optional[str]:
    """Loads result from GCS for query context."""
    if not BUCKET_NAME: return None
    client = get_storage_client()
    if not client: return None
    
    try:
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"tasks/{task_id}/result.json")
        if blob.exists():
            data = json.loads(blob.download_as_text())
            return data.get("result", "")
    except Exception:
        pass
    return None

# --- Background Processing ---

def process_audio_task(task_id: str, audio_blob_name: str, prompt_override: str = None):
    """Background task to process audio with Gemini."""
    logger.info(f"Processing task {task_id}")
    
    status = {
        "task_id": task_id,
        "status": "processing",
        "progress": 10,
        "message": "Initializing...",
        "created_at": time.time()
    }
    save_task_status(task_id, status)
    
    try:
        if not model:
            raise Exception("Vertex AI model not initialized")
        
        if not BUCKET_NAME:
            raise Exception("BUCKET_NAME not configured")

        # 1. Verify Audio in GCS
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(audio_blob_name)
        
        if not blob.exists():
            raise Exception(f"Audio file not found: {audio_blob_name}")
            
        gs_uri = f"gs://{BUCKET_NAME}/{audio_blob_name}"
        logger.info(f"Audio URI: {gs_uri}")

        status["progress"] = 30
        status["message"] = "Sending to Gemini 1.5 Pro..."
        save_task_status(task_id, status)

        # 2. Call Gemini
        audio_part = Part.from_uri(uri=gs_uri, mime_type="audio/mpeg")
        
        default_prompt = """
        תמלל את קובץ השמע הזה לעברית בצורה מלאה ומדויקת.
        הפרד בין הדוברים (למשל: דובר 1, דובר 2).
        הוסף חותמות זמן (timestamps) לפני כל פסקה.
        
        בסוף התמלול, הוסף ניתוח קצר בפורמט JSON:
        {
          "summary": "סיכום קצר של השיחה",
          "topics": ["נושא 1", "נושא 2"],
          "sentiment": "חיובי/שלילי/ניטרלי"
        }
        """
        
        prompt = prompt_override or default_prompt
        
        status["progress"] = 50
        status["message"] = "Generating transcript..."
        save_task_status(task_id, status)

        response = model.generate_content([audio_part, prompt])
        result_text = response.text
        
        # 3. Save Results
        save_result_to_gcs(task_id, result_text)
        
        # 4. Optional: Cleanup Audio
        try:
            blob.delete()
            logger.info(f"Deleted temp audio {audio_blob_name}")
        except:
            pass
            
        status["status"] = "completed"
        status["progress"] = 100
        status["message"] = "Processing complete"
        status["transcript_text"] = result_text # Simplified for now
        save_task_status(task_id, status)
        logger.info(f"Task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        status["status"] = "error"
        status["error"] = str(e)
        save_task_status(task_id, status)

def download_and_process_url(task_id: str, url: str):
    """Background task for URL download -> Upload -> Process."""
    status = {
        "task_id": task_id,
        "status": "processing",
        "progress": 5,
        "message": "Downloading video...",
        "created_at": time.time()
    }
    save_task_status(task_id, status)
    
    safe_temp = os.environ.get("TEMP", "/tmp")
    audio_filename = f"audio_{task_id}.mp3"
    audio_path = os.path.join(safe_temp, audio_filename)
    
    try:
        # Download
        logger.info(f"Downloading from {url}")
        cmd = [
            "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "4",
            "-o", audio_path.replace(".mp3", ".%(ext)s"),
            "--no-playlist", "--no-warnings", "--quiet",
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        
        if res.returncode != 0:
            raise Exception(f"Download failed: {res.stderr}")

        # Locate file
        if not os.path.exists(audio_path):
            found = [f for f in os.listdir(safe_temp) if f.startswith(f"audio_{task_id}") and f.endswith(".mp3")]
            if found:
                audio_path = os.path.join(safe_temp, found[0])
            else:
                raise Exception("Downloaded file not found")

        # Upload to GCS
        status["progress"] = 20
        status["message"] = "Uploading to Cloud Storage..."
        save_task_status(task_id, status)

        if not BUCKET_NAME:
            raise Exception("BUCKET_NAME not set")
            
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob_name = f"uploads/{task_id}.mp3"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(audio_path, timeout=600)
        
        # Cleanup local
        try:
            os.remove(audio_path)
        except: pass

        # Chain to processing
        process_audio_task(task_id, blob_name)

    except Exception as e:
        logger.error(f"URL Task {task_id} failed: {e}")
        status["status"] = "error"
        status["error"] = str(e)
        save_task_status(task_id, status)

# --- Routes ---

@app.get("/")
async def read_root():
    # Try to serve the main index page
    index_path = "templates/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return FileResponse("static/index.html")

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Async upload endpoint."""
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Server misconfigured: BUCKET_NAME missing")
    
    task_id = str(uuid.uuid4())[:8]
    blob_name = f"uploads/{task_id}_{file.filename}"
    
    try:
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, timeout=600)
        
        background_tasks.add_task(process_audio_task, task_id, blob_name)
        return {"task_id": task_id, "status": "queued"}
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start")
async def start_url_processing(background_tasks: BackgroundTasks, request: UrlRequest):
    """Async URL processing endpoint."""
    task_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(download_and_process_url, task_id, request.url)
    return {"task_id": task_id, "status": "queued"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Get task status."""
    status = load_task_status(task_id)
    if "error" in status:
        if status["error"] == "Task not found":
             # It might be just starting
             return {"status": "starting", "progress": 0}
        return JSONResponse(status_code=500, content=status)
    return status

@app.get("/download/{task_id}")
async def get_download(task_id: str):
    """Download transcript (placeholder)."""
    result = load_result_from_gcs(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # In a real app we might generate a TXT file or PDF
    # For now, return as plain text response suitable for browser view
    return JSONResponse(content={"text": result})

@app.get("/player/{task_id}", response_class=HTMLResponse)
async def player_page(request: Request, task_id: str):
    return templates.TemplateResponse("player.html", {"request": request, "task_id": task_id})

@app.post("/ask")
async def ask_question(request: AskRequest):
    """Chat with the transcript context."""
    if not model:
        raise HTTPException(status_code=503, detail="AI Service unavailable")
        
    context = load_result_from_gcs(request.task_id)
    if not context:
        raise HTTPException(status_code=404, detail="Context not found for this task")
        
    try:
        chat_prompt = f"""
        Context (Transcript):
        {context[:30000]}... (truncated)
        
        User Question: {request.question}
        
        Answer based only on the context provided.
        """
        response = model.generate_content(chat_prompt)
        return {"answer": response.text}
    except Exception as e:
        logger.error(f"Ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_study_material")
async def generate_study_material(request: AskRequest): 
    # Reuse AskRequest for task_id, question ignored
    # Placeholder for the study material generation logic
    # In a full impl this would call Gemini with specific JSON structure prompt
    return {
        "summary": "This is a placeholder summary generated by the system.",
        "key_points": ["Point 1", "Point 2", "Point 3"],
        "quiz": [
            {
                "question": "Sample Question?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
                "explanation": "Because A is correct."
            }
        ]
    }

