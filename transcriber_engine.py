"""
Transcription Engine - Core processing logic for audio transcription.

Handles downloading, transcription via Whisper, speaker diarization,
and AI-powered summaries. Runs as a background worker with task queue.
"""
# Standard library
import atexit
import json
import logging
import os
import queue
import threading
import time
import uuid

# Third-party
import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from faster_whisper import WhisperModel
import google.generativeai as genai

# Optional dependencies
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

# Configuration constants
TASKS_FILE = "tasks_state.json"
DOWNLOAD_FOLDER = "downloads"
WHISPER_MODEL = "small"  # Options: tiny, small, medium, large-v3 (small = best speed/quality)
DEFAULT_LANGUAGE = "he"
CLEANUP_RETENTION_HOURS = 24


class TranscriptionManager:
    """
    Background worker that processes transcription tasks from a queue.
    
    Supports URL downloads (via yt-dlp), local file uploads, optional
    speaker diarization, and AI-powered summaries via Google Gemini.
    """
    
    def __init__(self, test_mode=False, hf_token=None):
        self.task_queue = queue.Queue()
        self.tasks = {}
        self.lock = threading.Lock()
        self.test_mode = test_mode
        self.hf_token = hf_token or os.getenv('HF_TOKEN')
        
        # Auto-shutdown config (for cloud deployments)
        self.idle_start_time = time.time()
        self.idle_timeout = int(os.getenv('IDLE_TIMEOUT_MINUTES', '15'))
        self.auto_shutdown = os.getenv('AUTO_SHUTDOWN', 'false').lower() == 'true'
        
        self._load_tasks()
        self._fix_zombie_tasks()
        
        if not test_mode:
            self._init_whisper_model()
            self._init_diarization()
        else:
            self.model = None
            self.diarization_pipeline = None
        
        self._start_worker()
        self._start_scheduler()
        atexit.register(self._shutdown)

    def _fix_zombie_tasks(self):
        """Mark tasks that were processing when server crashed as errors."""
        active_states = ('downloading', 'transcribing', 'analyzing', 'queued')
        with self.lock:
            for task_id, task in self.tasks.items():
                if task.get('status') in active_states:
                    logger.warning(f"Found zombie task {task_id}, marking as error")
                    task['status'] = 'error'
                    task['message'] = 'Server restarted during processing'
                    task['progress'] = 0
            self._save_tasks()

    def _init_whisper_model(self):
        """Initialize Whisper model with GPU/CPU auto-detection."""
        use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
        
        if torch and torch.cuda.is_available() and use_gpu:
            device = "cuda"
            compute_type = "float16"
            logger.info(f"GPU Mode: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            compute_type = "int8"
            cpu_threads = int(os.getenv('CPU_THREADS', str(os.cpu_count() or 4)))
            logger.info(f"CPU Mode: Using {cpu_threads} threads")
        
        logger.info(f"Loading Whisper model ({WHISPER_MODEL}) on {device}...")
        
        if device == "cuda":
            self.model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
        else:
            cpu_threads = int(os.getenv('CPU_THREADS', str(os.cpu_count() or 4)))
            self.model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type, cpu_threads=cpu_threads)

    def _init_diarization(self):
        """Initialize speaker diarization pipeline if available."""
        self.diarization_pipeline = None
        
        if not self.hf_token:
            logger.info("Diarization disabled (no HF_TOKEN)")
            return
            
        if not PYANNOTE_AVAILABLE:
            logger.info("Diarization disabled (pyannote.audio not installed)")
            return
        
        logger.info("Loading speaker diarization pipeline...")
        try:
            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=self.hf_token  # Changed from use_auth_token
            )
            if torch:
                self.diarization_pipeline.to(torch.device("cpu"))
            logger.info("Diarization loaded successfully")
        except Exception as e:
            logger.warning(f"Diarization disabled: {e}")

    def _start_worker(self):
        """Start background worker thread."""
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

    def _start_scheduler(self):
        """Start background scheduler for cleanup and idle monitoring."""
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._cleanup_old_files, 'interval', hours=1)
        
        if self.auto_shutdown:
            logger.info(f"Auto-shutdown enabled: {self.idle_timeout} min timeout")
            self.scheduler.add_job(self._check_idle, 'interval', minutes=1)
        
        self.scheduler.start()

    # --- Public API ---
    
    def submit_task(self, url=None, file_path=None, test_mode=None):
        """Submit a new transcription task. Returns task_id."""
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                'status': 'queued',
                'progress': 0,
                'message': 'Waiting...',
                'created_at': time.time(),
                'url': url,
                'filename': None
            }
        self.task_queue.put((task_id, url, file_path, test_mode))
        return task_id

    def get_status(self, task_id):
        """Get current status of a task."""
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self):
        """Get all tasks (for history view)."""
        with self.lock:
            return dict(self.tasks)

    # --- Worker Logic ---

    def _worker_loop(self):
        """Main worker loop - processes tasks from queue."""
        while True:
            task_id, url, file_path, test_mode = self.task_queue.get()
            try:
                self._process_task(task_id, url, file_path, test_mode)
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                self._update_task(task_id, 'error', 0, str(e))
            finally:
                self.task_queue.task_done()

    def _process_task(self, task_id, url, file_path, test_mode):
        """Process a single transcription task."""
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        
        # Test mode - return dummy data
        if test_mode or self.test_mode:
            self._run_test_mode(task_id)
            return
        
        # Step 1: Download audio
        audio_file = self._download_audio(task_id, url, file_path)
        
        # Step 2: Transcribe
        segments, full_text = self._transcribe(task_id, audio_file)
        
        # Step 3: Speaker diarization (optional)
        if self.diarization_pipeline:
            self._identify_speakers(task_id, audio_file, segments)
        
        # Step 4: AI summary
        self._update_task(task_id, 'analyzing', 90, 'Generating summary...')
        summary = self._generate_summary(full_text)
        
        # Save results
        self._save_results(audio_file, segments, full_text)
        self._update_task(
            task_id, 'completed', 100, 'Done!',
            filename=audio_file.replace('.wav', '.txt'),
            text=full_text,
            summary=summary,
            segments=segments
        )
        
        # Cleanup downloaded file
        if url and os.path.exists(audio_file):
            os.remove(audio_file)

    def _run_test_mode(self, task_id):
        """Simulate transcription for testing."""
        logger.info("Running in TEST MODE")
        self._update_task(task_id, 'downloading', 10, '[TEST] Simulating...')
        time.sleep(0.5)
        self._update_task(task_id, 'transcribing', 50, '[TEST] Processing...')
        time.sleep(0.5)
        self._update_task(
            task_id, 'completed', 100, '[TEST] Done!',
            filename='test_output.txt',
            text='Test transcription content.',
            summary={'title': 'Test', 'summary': 'Test summary', 'tags': ['test']},
            segments=[{'start': 0, 'end': 1, 'text': 'Test', 'speaker': 'SPEAKER_00'}]
        )

    def _download_audio(self, task_id, url, file_path):
        """Download and convert audio to WAV format."""
        self._update_task(task_id, 'downloading', 10, 'Downloading...')
        
        if file_path:
            return file_path
        
        # TODO: Add support for direct MP4 file handling
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '0',
            }],
            'postprocessor_args': ['-ar', '16000', '-ac', '1'],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).rsplit('.', 1)[0] + ".wav"

    def _transcribe(self, task_id, audio_file):
        """Run Whisper transcription."""
        self._update_task(task_id, 'transcribing', 30, 'Transcribing...')
        
        segments_gen, _ = self.model.transcribe(
            audio_file,
            beam_size=1,
            language=DEFAULT_LANGUAGE,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            no_speech_threshold=0.7,  # Skip silence faster
            compression_ratio_threshold=3.0,  # Skip problematic segments (music, noise)
            log_prob_threshold=-1.5,  # Be more lenient with low-confidence segments
        )
        
        segments = []
        full_text = ""
        for seg in segments_gen:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "speaker": "UNKNOWN"
            })
            full_text += seg.text + " "
        
        return segments, full_text.strip()

    def _identify_speakers(self, task_id, audio_file, segments):
        """Run speaker diarization and merge with transcription."""
        self._update_task(task_id, 'transcribing', 60, 'Identifying speakers...')
        
        try:
            diarization = self.diarization_pipeline(audio_file)
            
            for segment in segments:
                mid_time = (segment["start"] + segment["end"]) / 2
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    if turn.start <= mid_time <= turn.end:
                        segment["speaker"] = speaker
                        break
        except Exception as e:
            logger.error(f"Diarization error: {e}")

    def _generate_summary(self, text):
        """Generate AI summary using Gemini."""
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Analyze this Hebrew text. Return JSON {{'title': '', 'summary': '', 'tags': []}}: {text[:8000]}"
            response = model.generate_content(prompt)
            return json.loads(response.text.replace('```json', '').replace('```', ''))
        except Exception:
            return None

    # --- Internal Helpers ---

    def _update_task(self, task_id, status, progress, message, **kwargs):
        """Update task status in memory and persist to disk."""
        with self.lock:
            self.tasks[task_id].update({
                'status': status,
                'progress': progress,
                'message': message,
                **kwargs
            })
        self._save_tasks()

    def _save_tasks(self):
        """Persist tasks to JSON file."""
        with open(TASKS_FILE, 'w') as f:
            json.dump(self.tasks, f)

    def _load_tasks(self):
        """Load tasks from JSON file."""
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, 'r') as f:
                    self.tasks = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.tasks = {}

    def _save_results(self, filename, segments, text):
        """Save transcript text and segments to files."""
        base = os.path.splitext(filename)[0]
        with open(f"{base}.txt", 'w', encoding='utf-8') as f:
            f.write(text)
        with open(f"{base}_segments.json", 'w', encoding='utf-8') as f:
            json.dump({'segments': segments}, f, ensure_ascii=False)

    # --- Maintenance ---

    def _cleanup_old_files(self):
        """Delete files older than retention period."""
        logger.info("Running disk cleanup...")
        retention = int(os.getenv('CLEANUP_RETENTION_HOURS', str(CLEANUP_RETENTION_HOURS)))
        cutoff = time.time() - (retention * 3600)
        deleted = 0
        
        if os.path.exists(DOWNLOAD_FOLDER):
            for fname in os.listdir(DOWNLOAD_FOLDER):
                fpath = os.path.join(DOWNLOAD_FOLDER, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    try:
                        os.remove(fpath)
                        deleted += 1
                    except OSError as e:
                        logger.error(f"Error deleting {fname}: {e}")
        
        logger.info(f"Cleanup complete: deleted {deleted} files")

    def _check_idle(self):
        """Check if server should auto-shutdown due to idle timeout."""
        with self.lock:
            active = sum(1 for t in self.tasks.values() if t.get('status') not in ('completed', 'error'))
        
        if active == 0 and self.task_queue.qsize() == 0:
            idle_minutes = (time.time() - self.idle_start_time) / 60
            
            if idle_minutes >= self.idle_timeout:
                self._trigger_shutdown()
        else:
            self.idle_start_time = time.time()

    def _trigger_shutdown(self):
        """Trigger server shutdown (respects DRY_RUN setting)."""
        dry_run = os.getenv('SHUTDOWN_DRY_RUN', 'true').lower() == 'true'
        
        if dry_run:
            logger.warning("SHUTDOWN TRIGGERED (DRY-RUN - no actual shutdown)")
        else:
            logger.warning("INITIATING SERVER SHUTDOWN...")
            time.sleep(10)
            os.system("shutdown -h now")

    def _shutdown(self):
        """Cleanup on application exit."""
        self.scheduler.shutdown(wait=False)