import threading
import queue
import uuid
import os
import time
import json
import glob
import logging
import atexit
import signal
from datetime import datetime, timedelta
import yt_dlp
from faster_whisper import WhisperModel
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

class TranscriptionManager:
    """
    Optimized Transcription Engine for Production
    Features:
    - Audio-only download (saves bandwidth)
    - Faster-Whisper (4x speed on CPU)
    - Auto-Cleanup (Janitor)
    - Task persistence (survives restarts)
    """
    
    TASKS_FILE = "tasks_state.json"  # Persistence file for crash recovery
    
    def __init__(self, test_mode=False, hf_token=None):
        self.task_queue = queue.Queue()
        self.tasks = {}
        self.lock = threading.Lock()
        self.test_mode = test_mode
        self.hf_token = hf_token  # For future speaker diarization
        
        # Load persisted tasks from disk
        self._load_tasks()
        
        # Load Model Once (Global) - Optimized for CPU + Speed
        # Options: 'tiny' (fast), 'base' (balanced), 'small', 'medium', 'large-v3' (accurate)
        if not test_mode:
            logger.info("Loading Faster-Whisper model (tiny - speed optimized)...")
            self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded successfully")
        else:
            self.model = None
        
        # Start Worker
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

        # Start Janitor (Cleanup every hour)
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._cleanup_old_files, 'interval', hours=1)
        self.scheduler.start()
        
        # Graceful shutdown
        atexit.register(self._shutdown)
        signal.signal(signal.SIGTERM, lambda s, f: self._shutdown())
    
    def submit_task(self, url=None, file_path=None, test_mode=None):
        if not url and not file_path:
            raise ValueError("Must provide either 'url' or 'file_path'")
        
        effective_test_mode = test_mode if test_mode is not None else self.test_mode
        task_id = str(uuid.uuid4())
        
        with self.lock:
            self.tasks[task_id] = {
                'status': 'queued',
                'progress': 0,
                'message': 'Waiting in queue...',
                'created_at': time.time(),
                'test_mode': effective_test_mode,
                'url': url,
                'filename': None
            }
        
        self.task_queue.put((task_id, url, file_path, effective_test_mode))
        return task_id

    def get_status(self, task_id):
        with self.lock:
            return self.tasks.get(task_id, None)

    def get_all_tasks(self):
        with self.lock:
            return dict(self.tasks)

    def _worker_loop(self):
        """Main worker loop - processes tasks from the queue."""
        while True:
            task_id = None
            try:
                task_id, url, file_path, test_mode = self.task_queue.get()
                self._process_task(task_id, url, file_path, test_mode)
            except Exception as e:
                logger.exception(f"Worker error (task_id={task_id}): {e}")
                if task_id:
                    self._update(task_id, 'error', 0, f"Internal error: {str(e)}")
            finally:
                self.task_queue.task_done()

    def _process_task(self, task_id, url, file_path, test_mode):
        if test_mode:
            self._simulate_task(task_id)
            return

        download_folder = "downloads"
        os.makedirs(download_folder, exist_ok=True)
        
        audio_file = None
        
        try:
            # === PHASE 1: SMART DOWNLOAD (Audio Only) ===
            if url:
                self._update(task_id, 'downloading', 10, 'Downloading audio stream...')
                
                # Optimized yt-dlp for Audio Only
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # Filename after ffmpeg conversion
                    base_filename = ydl.prepare_filename(info).rsplit('.', 1)[0]
                    audio_file = f"{base_filename}.mp3"
            
            else:
                # File Upload Case
                self._update(task_id, 'processing', 20, 'Processing uploaded file...')
                audio_file = file_path

            if not os.path.exists(audio_file):
                raise Exception("Audio file not found")

            # === PHASE 2: FAST TRANSCRIPTION (Speed Optimized) ===
            self._update(task_id, 'transcribing', 40, 'AI Transcribing (Faster-Whisper)...')
            
            # Speed optimizations: beam_size=1, VAD filter skips silence
            segments, info = self.model.transcribe(
                audio_file, 
                beam_size=1,  # Faster (was 5)
                language="he",
                vad_filter=True,  # Skip silent parts
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Live progress update based on segments is hard without duration, 
            # so we just iterate.
            transcript_text = ""
            for segment in segments:
                transcript_text += segment.text + "\n"
            
            self._update(task_id, 'finalizing', 90, 'Saving transcript...')
            
            # Save Text
            base_name = os.path.splitext(audio_file)[0]
            text_file = f"{base_name}.txt"
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            
            # === PHASE 3: GEMINI ANALYSIS ===
            self._update(task_id, 'analyzing', 95, 'Generating AI Summary...')
            ai_summary = self._analyze_with_gemini(transcript_text, text_file)

            # Cleanup Source Audio (Save space)
            if url and os.path.exists(audio_file):
                os.remove(audio_file)

            self._update(task_id, 'completed', 100, 'Done!', 
                         filename=text_file, text=transcript_text, summary=ai_summary)

        except Exception as e:
            logger.exception(f"Task failed (task_id={task_id}): {e}")
            self._update(task_id, 'error', 0, f"Error: {str(e)}")

    def _update(self, task_id, status, progress, message, filename=None, text=None, summary=None, segments=None):
        """Update task status. Only updates fields that are not None."""
        with self.lock:
            if task_id not in self.tasks:
                logger.warning(f"Attempted to update non-existent task: {task_id}")
                return
            
            update_data = {
                'status': status,
                'progress': progress,
                'message': message,
            }
            # Only update optional fields if not None
            if filename is not None:
                update_data['filename'] = filename
            if text is not None:
                update_data['transcript_text'] = text
            if summary is not None:
                update_data['ai_summary'] = summary
            if segments is not None:
                update_data['transcript_segments'] = segments
            
            self.tasks[task_id].update(update_data)
        # Persist to disk after every update
        self._save_tasks()
    
    def _save_tasks(self):
        """Persist tasks to JSON file for crash recovery"""
        with self.lock:
            try:
                with open(self.TASKS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.tasks, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Could not save tasks to disk: {e}")
    
    def _load_tasks(self):
        """Load tasks from JSON file on startup"""
        if os.path.exists(self.TASKS_FILE):
            try:
                with open(self.TASKS_FILE, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
                logger.info(f"Loaded {len(self.tasks)} tasks from disk")
            except Exception as e:
                logger.warning(f"Could not load tasks from disk: {e}")
                self.tasks = {}

    def _analyze_with_gemini(self, text, text_file):
        """Generates Title, Tags, Summary"""
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key: return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            Analyze this Hebrew transcript. Return JSON ONLY:
            {{
                "title": "Short Title",
                "tags": ["#tag1", "#tag2"],
                "summary": "2 sentences summary"
            }}
            Text: {text[:4000]}
            """
            response = model.generate_content(prompt)
            clean_json = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)
            
            # Save metadata
            meta_file = text_file.replace('.txt', '_metadata.json')
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            return data
        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            return None

    def _cleanup_old_files(self):
        """Janitor: Deletes files older than 24 hours"""
        logger.info("Janitor: Cleaning up old files...")
        folders = ["downloads", "uploads"]
        cutoff = time.time() - (24 * 3600)
        deleted_count = 0
        
        for folder in folders:
            if not os.path.exists(folder): 
                continue
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path):
                    if os.path.getmtime(path) < cutoff:
                        try:
                            os.remove(path)
                            deleted_count += 1
                            logger.debug(f"Deleted old file: {f}")
                        except Exception as e:
                            logger.warning(f"Error deleting {f}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Janitor: Deleted {deleted_count} old files")
    
    def _shutdown(self):
        """Graceful shutdown handler."""
        logger.info("Shutting down TranscriptionManager...")
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as e:
            logger.warning(f"Error shutting down scheduler: {e}")

    def _simulate_task(self, task_id):
        """For testing UI without running AI"""
        steps = [
            ('downloading', 20, 'Simulating download...'),
            ('transcribing', 50, 'Simulating AI...'),
            ('analyzing', 80, 'Simulating Gemini...'),
            ('completed', 100, 'Done!')
        ]
        for status, prog, msg in steps:
            self._update(task_id, status, prog, msg)
            time.sleep(1)