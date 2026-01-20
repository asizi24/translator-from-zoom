import os
import json
import logging
import uuid
import time
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# הגדרות
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
# שים לב: השם הזה חייב להיות זהה לשם שיוגדר ב-setup.sh
BUCKET_NAME = os.environ.get("BUCKET_NAME", "zoom-audio-hybrid-store") 
LOCATION = "us-central1"

app = FastAPI()

# חיבור לממשק הישן (Static & Templates)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")
else:
    templates = None

# אתחול גוגל
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
    storage_client = storage.Client()
except Exception as e:
    logger.error(f"Failed to init GCP: {e}")

# --- דפים (Frontend Routes) ---

@app.get("/")
async def index(request: Request):
    """דף הבית (העלאת קובץ)"""
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return "Error: Templates not found. Please run locally with correct folder structure."

@app.get("/player/{task_id}")
async def player(request: Request, task_id: str):
    """דף הנגן/צ'אט"""
    if templates:
        return templates.TemplateResponse("player.html", {"request": request, "task_id": task_id})
    return "Error: Templates not found"

# --- API (Backend Logic) ---

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    1. מעלה אודיו לדלי (Bucket)
    2. שולח לג'ימיני (Vertex AI)
    3. שומר את ה-JSON בדלי
    """
    task_id = str(uuid.uuid4())
    
    try:
        if not PROJECT_ID:
            raise HTTPException(status_code=500, detail="GCP Project ID not configured")

        # א. העלאת אודיו
        audio_filename = f"uploads/{task_id}_{file.filename}"
        bucket = storage_client.bucket(BUCKET_NAME)
        audio_blob = bucket.blob(audio_filename)
        audio_blob.upload_from_file(file.file, content_type=file.content_type)
        gcs_uri = f"gs://{BUCKET_NAME}/{audio_filename}"
        logger.info(f"Uploaded audio to {gcs_uri}")
        
        # ב. שליחה לג'ימיני (פרומפט מותאם לממשק הישן)
        model = GenerativeModel("gemini-1.5-pro")
        audio_part = Part.from_uri(uri=gcs_uri, mime_type=file.content_type or "audio/mpeg")
        
        prompt = """
        נתח את ההקלטה הזו כמורה פרטי. המטרה היא לייצר סיכום לימודי.
        החזר JSON בלבד (ללא markdown) במבנה הבא:
        {
            "transcript_text": "תקציר מפורט וכרונולוגי של תוכן השיעור (כיוון שאין תמלול מלא)",
            "summary": "סיכום קצר של 3 פסקאות",
            "key_points": ["נקודה 1", "נקודה 2", "נקודה 3"],
            "quiz": [
                {
                    "question": "שאלה?",
                    "options": ["א", "ב", "ג", "ד"],
                    "correct_index": 0,
                    "explanation": "הסבר"
                }
            ]
        }
        """
        
        logger.info("Sending to Gemini...")
        response = model.generate_content([audio_part, prompt], generation_config={"response_mime_type": "application/json"})
        result_json = response.text

        # ג. שמירת התוצאה בדלי
        result_filename = f"results/{task_id}.json"
        result_blob = bucket.blob(result_filename)
        result_blob.upload_from_string(result_json, content_type="application/json")
        logger.info(f"Saved result to {result_filename}")

        # הפניה לנגן
        return {"task_id": task_id, "status": "completed", "redirect_url": f"/player/{task_id}"}

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """הנגן מושך מפה את הנתונים"""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"results/{task_id}.json")
        
        if not blob.exists():
            return {"status": "processing"}
            
        json_data = blob.download_as_text()
        data = json.loads(json_data)
        
        return {
            "status": "completed",
            "transcript_text": data.get("transcript_text", ""),
            "summary": data.get("summary", ""),
            "key_points": data.get("key_points", []),
            "quiz": data.get("quiz", [])
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
