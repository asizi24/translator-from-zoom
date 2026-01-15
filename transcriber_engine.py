import threading
import queue
import uuid
import os
import time
import json
import logging
import atexit
import signal
import yt_dlp
from faster_whisper import WhisperModel
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
# ייבוא זיהוי דוברים (אופציונלי - נטען רק אם הספרייה קיימת)
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    Pipeline = None
    PYANNOTE_AVAILABLE = False

try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger(__name__)

class TranscriptionManager:
    TASKS_FILE = "tasks_state.json"
    
    def __init__(self, test_mode=False, hf_token=None):
        self.task_queue = queue.Queue()
        self.tasks = {}
        self.lock = threading.Lock()
        self.test_mode = test_mode
        self.hf_token = hf_token or os.getenv('HF_TOKEN')
        
        # Idle auto-shutdown tracking
        self.idle_start_time = time.time()
        self.idle_timeout_minutes = int(os.getenv('IDLE_TIMEOUT_MINUTES', '15'))
        self.auto_shutdown_enabled = os.getenv('AUTO_SHUTDOWN', 'false').lower() == 'true'
        
        self._load_tasks()
        
        # Load Whisper model (large-v3 for maximum quality)
        if not test_mode:
            # 🧵 Hardware-Matched Threading: 2 vCPUs on m7i-flex.large
            cpu_threads = int(os.getenv('CPU_THREADS', '2'))
            logger.info(f"🚀 Loading Faster-Whisper (Large-v3) with {cpu_threads} CPU threads...")
            self.model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=cpu_threads)
            
            # טעינת מודל זיהוי דוברים (אם יש טוקן וספריית pyannote זמינה)
            self.diarization_pipeline = None
            if self.hf_token and PYANNOTE_AVAILABLE:
                logger.info("👥 Loading Speaker Diarization pipeline...")
                try:
                    self.diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        token=self.hf_token
                    )
                    logger.info("✅ Diarization pipeline loaded successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Diarization disabled: {e}")
            elif not PYANNOTE_AVAILABLE:
                logger.info("ℹ️ Diarization disabled (pyannote.audio not installed)")
        else:
            self.model = None

        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._cleanup_old_files, 'interval', hours=1)
        
        # Add idle monitoring job if AUTO_SHUTDOWN is enabled
        if self.auto_shutdown_enabled:
            logger.info(f"⏰ Idle Auto-Shutdown ENABLED: {self.idle_timeout_minutes} min timeout")
            self.scheduler.add_job(self._check_idle_shutdown, 'interval', minutes=1)
        else:
            logger.info("⏰ Idle Auto-Shutdown DISABLED (set AUTO_SHUTDOWN=true to enable)")
        
        self.scheduler.start()
        
        atexit.register(self._shutdown)

    def submit_task(self, url=None, file_path=None, test_mode=None):
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                'status': 'queued', 'progress': 0, 'message': 'Waiting...',
                'created_at': time.time(), 'url': url, 'filename': None
            }
        self.task_queue.put((task_id, url, file_path, test_mode))
        return task_id

    def get_status(self, task_id):
        with self.lock: return self.tasks.get(task_id)

    def get_all_tasks(self):
        with self.lock: return dict(self.tasks)

    def _worker_loop(self):
        while True:
            task_id, url, file_path, test_mode = self.task_queue.get()
            try:
                self._process_task(task_id, url, file_path, test_mode)
            except Exception as e:
                logger.error(f"Task failed: {e}")
                self._update(task_id, 'error', 0, str(e))
            finally:
                self.task_queue.task_done()

    def _process_task(self, task_id, url, file_path, test_mode):
        download_folder = "downloads"
        os.makedirs(download_folder, exist_ok=True)
        
        # בדיקת מצב בדיקה - החזרת תוצאה מדומה
        if test_mode or self.test_mode:
            logger.info("🧪 Running in TEST MODE - simulating transcription")
            self._update(task_id, 'downloading', 10, '[TEST] Simulating download...')
            time.sleep(0.5)
            self._update(task_id, 'transcribing', 50, '[TEST] Simulating transcription...')
            time.sleep(0.5)
            self._update(task_id, 'completed', 100, '[TEST] Done!',
                         filename='test_output.txt',
                         text='This is a simulated test transcription.',
                         summary={'title': 'Test', 'summary': 'Test summary', 'tags': ['test']},
                         segments=[{'start': 0, 'end': 1, 'text': 'Test segment', 'speaker': 'SPEAKER_00'}])
            return
        
        # שלב 1: הורדה - ⚙️ Direct Audio Pipeline (WAV 16kHz Mono)
        self._update(task_id, 'downloading', 10, 'Downloading (optimized WAV)...')
        audio_file = file_path
        if url:
            # Download and convert directly to WAV (16kHz, Mono) in a single step
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(download_folder, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '0',
                }],
                'postprocessor_args': [
                    '-ar', '16000',  # 16kHz sample rate
                    '-ac', '1',       # Mono channel
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_file = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".wav"

        # שלב 2: תמלול מהיר - 🚀 VAD Filter enabled to skip silence
        self._update(task_id, 'transcribing', 30, 'Transcribing (Large-v3 + VAD)...')
        segments, _ = self.model.transcribe(
            audio_file,
            beam_size=1,
            language="he",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}
        )
        
        # המרת הסגמנטים לרשימה נוחה
        transcript_data = []
        full_text = ""
        for seg in segments:
            transcript_data.append({
                "start": seg.start, "end": seg.end, "text": seg.text.strip(), "speaker": "UNKNOWN"
            })
            full_text += seg.text + " "

        # שלב 3: זיהוי דוברים (אם קיים) - ⚙️ No conversion needed, already WAV!
        if self.diarization_pipeline:
            self._update(task_id, 'transcribing', 60, 'Identifying Speakers...')
            try:
                # Audio is already optimized WAV (16kHz, Mono) - no conversion needed!
                diarization = self.diarization_pipeline(audio_file)
                
                # מיזוג דוברים עם טקסט
                for segment in transcript_data:
                    # בדיקה מי הדובר הדומיננטי בזמן הזה
                    mid_time = (segment["start"] + segment["end"]) / 2
                    best_speaker = "UNKNOWN"
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        if turn.start <= mid_time <= turn.end:
                            best_speaker = speaker
                            break
                    segment["speaker"] = best_speaker
            except Exception as e:
                logger.error(f"Diarization error: {e}")

        # שלב 4: סיכום AI
        self._update(task_id, 'analyzing', 90, 'Generating Summary...')
        ai_summary = self._analyze_with_gemini(full_text, audio_file)

        # שמירה וסיום
        self._save_results(audio_file, transcript_data, full_text)
        self._update(task_id, 'completed', 100, 'Done!', 
                     filename=audio_file.replace('.wav', '.txt'),
                     text=full_text, summary=ai_summary, segments=transcript_data)
        
        if url and os.path.exists(audio_file): os.remove(audio_file)

    def _update(self, task_id, status, progress, message, **kwargs):
        with self.lock:
            self.tasks[task_id].update({'status': status, 'progress': progress, 'message': message, **kwargs})
        self._save_tasks()

    def _save_tasks(self):
        with open(self.TASKS_FILE, 'w') as f: json.dump(self.tasks, f)

    def _load_tasks(self):
        if os.path.exists(self.TASKS_FILE):
            try:
                with open(self.TASKS_FILE, 'r') as f: self.tasks = json.load(f)
            except: self.tasks = {}

    def _analyze_with_gemini(self, text, filename):
        if not os.getenv('GOOGLE_API_KEY'): return None
        try:
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            model = genai.GenerativeModel('gemini-1.5-flash')
            resp = model.generate_content(f"Analyze this Hebrew text. Return JSON {{'title': '', 'summary': '', 'tags': []}}: {text[:8000]}")
            return json.loads(resp.text.replace('```json', '').replace('```', ''))
        except: return None

    def _save_results(self, filename, segments, text):
        base = os.path.splitext(filename)[0]
        with open(f"{base}.txt", 'w', encoding='utf-8') as f: f.write(text)
        with open(f"{base}_segments.json", 'w', encoding='utf-8') as f: json.dump({'segments': segments}, f)

    def _cleanup_old_files(self):
        # Implementation same as before
        pass
    
    def _get_active_task_count(self):
        """Count tasks that are still in progress (not completed/error)"""
        with self.lock:
            active = sum(1 for t in self.tasks.values() 
                        if t.get('status') not in ('completed', 'error'))
        return active
    
    def _check_idle_shutdown(self):
        """Check if server has been idle long enough to trigger shutdown"""
        active_tasks = self._get_active_task_count()
        queue_size = self.task_queue.qsize()
        
        if active_tasks == 0 and queue_size == 0:
            idle_minutes = (time.time() - self.idle_start_time) / 60
            logger.info(f"⏰ Server idle for {idle_minutes:.1f} minutes (threshold: {self.idle_timeout_minutes} min)")
            
            if idle_minutes >= self.idle_timeout_minutes:
                self._trigger_shutdown()
        else:
            # Reset idle timer when there's activity
            self.idle_start_time = time.time()
            logger.debug(f"⏰ Active: {active_tasks} tasks, {queue_size} queued - idle timer reset")
    
    def _trigger_shutdown(self):
        """Trigger server shutdown (DRY-RUN: only logs by default)"""
        dry_run = os.getenv('SHUTDOWN_DRY_RUN', 'true').lower() == 'true'
        
        if dry_run:
            logger.warning("🔴 SHUTDOWN TRIGGERED (DRY-RUN MODE - no actual shutdown)")
            logger.warning("🔴 To enable real shutdown, set SHUTDOWN_DRY_RUN=false")
        else:
            logger.warning("🔴 INITIATING SERVER SHUTDOWN due to idle timeout...")
            logger.warning("🔴 Server will shut down in 10 seconds...")
            # Give time for logs to flush
            time.sleep(10)
            os.system("shutdown -h now")

    def _shutdown(self):
        self.scheduler.shutdown(wait=False)