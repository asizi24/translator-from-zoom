"""
Transcription Engine - Optimized for local desktop usage.

- Auto-detects GPU/CPU
- Handles stuck segments gracefully
- Real-time progress updates
- Robust error handling
"""
import atexit
import json
import logging
import os
import queue
import threading
import time
import uuid

import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from faster_whisper import WhisperModel
import google.generativeai as genai

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

# ============================================
# CONFIGURATION - Edit these for your needs
# ============================================
WHISPER_MODEL = "small"  # tiny=fastest, small=balanced, medium=quality, large-v3=best
DEFAULT_LANGUAGE = "he"
DOWNLOAD_FOLDER = "downloads"
TASKS_FILE = "tasks_state.json"
CLEANUP_HOURS = 24


class TranscriptionManager:
    """Background worker for transcription tasks."""
    
    def __init__(self, test_mode=False, hf_token=None):
        self.task_queue = queue.Queue()
        self.tasks = {}
        self.lock = threading.Lock()
        self.test_mode = test_mode
        self.hf_token = hf_token or os.getenv('HF_TOKEN')
        self.model = None
        self.diarization_pipeline = None
        
        # Cloud auto-shutdown (disabled for local)
        self.idle_start = time.time()
        self.idle_timeout = int(os.getenv('IDLE_TIMEOUT_MINUTES', '15'))
        self.auto_shutdown = os.getenv('AUTO_SHUTDOWN', 'false').lower() == 'true'
        
        self._load_tasks()
        self._fix_zombie_tasks()
        
        if not test_mode:
            self._init_models()
        
        self._start_background_services()
        atexit.register(self._shutdown)

    # --- Initialization ---
    
    def _init_models(self):
        """Load Whisper and optionally diarization."""
        self._init_whisper()
        self._init_diarization()
    
    def _init_whisper(self):
        """Initialize Whisper with optimal settings for current hardware."""
        use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
        
        if torch and torch.cuda.is_available() and use_gpu:
            device, compute_type = "cuda", "float16"
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        else:
            device, compute_type = "cpu", "int8"
            threads = int(os.getenv('CPU_THREADS', str(os.cpu_count() or 4)))
            logger.info(f"CPU: {threads} threads")
        
        logger.info(f"Loading {WHISPER_MODEL} on {device}...")
        
        if device == "cuda":
            self.model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
        else:
            threads = int(os.getenv('CPU_THREADS', str(os.cpu_count() or 4)))
            self.model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type, cpu_threads=threads)
    
    def _init_diarization(self):
        """Initialize speaker diarization if HF token available."""
        if not self.hf_token or not PYANNOTE_AVAILABLE:
            return
        
        try:
            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=self.hf_token
            )
            if torch:
                self.diarization_pipeline.to(torch.device("cpu"))
            logger.info("Diarization ready")
        except Exception as e:
            logger.warning(f"Diarization unavailable: {e}")
    
    def _fix_zombie_tasks(self):
        """Mark crashed tasks as errors."""
        with self.lock:
            for tid, task in self.tasks.items():
                if task.get('status') in ('downloading', 'transcribing', 'analyzing', 'queued'):
                    task.update({'status': 'error', 'message': 'Server restarted', 'progress': 0})
            self._save_tasks()
    
    def _start_background_services(self):
        """Start worker thread and scheduler."""
        threading.Thread(target=self._worker_loop, daemon=True).start()
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._cleanup_old_files, 'interval', hours=1)
        if self.auto_shutdown:
            self.scheduler.add_job(self._check_idle, 'interval', minutes=1)
        self.scheduler.start()

    # --- Public API ---
    
    def submit_task(self, url=None, file_path=None, test_mode=None):
        """Add task to queue. Returns task_id."""
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                'status': 'queued', 'progress': 0, 'message': 'Waiting...',
                'created_at': time.time(), 'url': url, 'filename': None
            }
        self.task_queue.put((task_id, url, file_path, test_mode))
        return task_id
    
    def get_status(self, task_id):
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self):
        with self.lock:
            return dict(self.tasks)

    # --- Worker ---
    
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
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        
        if test_mode or self.test_mode:
            return self._run_test(task_id)
        
        # Step 1: Download
        audio = self._download(task_id, url, file_path)
        
        # Step 2: Transcribe (with progress)
        segments, text = self._transcribe(task_id, audio)
        
        # Step 3: Diarization (optional)
        if self.diarization_pipeline:
            self._diarize(task_id, audio, segments)
        
        # Step 4: AI Summary
        self._update(task_id, 'analyzing', 90, 'AI summary...')
        summary = self._summarize(text)
        
        # Done
        self._save_results(audio, segments, text)
        self._update(task_id, 'completed', 100, 'Done!',
                     filename=audio.replace('.wav', '.txt'),
                     text=text, summary=summary, segments=segments)
        
        if url and os.path.exists(audio):
            os.remove(audio)
    
    def _run_test(self, task_id):
        self._update(task_id, 'downloading', 10, '[TEST]')
        time.sleep(0.3)
        self._update(task_id, 'transcribing', 50, '[TEST]')
        time.sleep(0.3)
        self._update(task_id, 'completed', 100, '[TEST] Done!',
                     filename='test.txt', text='Test.', summary=None,
                     segments=[{'start': 0, 'end': 1, 'text': 'Test', 'speaker': 'A'}])
    
    def _download(self, task_id, url, file_path):
        self._update(task_id, 'downloading', 10, 'Downloading...')
        
        if file_path:
            return file_path
        
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
            'postprocessor_args': ['-ar', '16000', '-ac', '1'],
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).rsplit('.', 1)[0] + ".wav"
    
    def _transcribe(self, task_id, audio):
        """Transcribe with real-time progress updates."""
        self._update(task_id, 'transcribing', 30, 'Starting transcription...')
        
        # Get audio duration for progress calculation
        try:
            import wave
            with wave.open(audio, 'rb') as w:
                duration = w.getnframes() / w.getframerate()
        except Exception:
            duration = 0
        
        segments_gen, _ = self.model.transcribe(
            audio,
            beam_size=1,
            language=DEFAULT_LANGUAGE,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            no_speech_threshold=0.7,
            compression_ratio_threshold=3.0,  # Skip stuck segments
            log_prob_threshold=-1.5,
        )
        
        segments = []
        text_parts = []
        last_update = 0
        
        for seg in segments_gen:
            segments.append({
                "start": seg.start, "end": seg.end,
                "text": seg.text.strip(), "speaker": "UNKNOWN"
            })
            text_parts.append(seg.text)
            
            # Update progress every 30 seconds of audio
            if duration > 0 and seg.end - last_update > 30:
                progress = min(30 + int((seg.end / duration) * 55), 85)
                mins = int(seg.end // 60)
                secs = int(seg.end % 60)
                self._update(task_id, 'transcribing', progress, f'{mins:02d}:{secs:02d} / {int(duration//60):02d}:{int(duration%60):02d}')
                last_update = seg.end
        
        return segments, " ".join(text_parts).strip()
    
    def _diarize(self, task_id, audio, segments):
        self._update(task_id, 'transcribing', 85, 'Identifying speakers...')
        try:
            diarization = self.diarization_pipeline(audio)
            for seg in segments:
                mid = (seg["start"] + seg["end"]) / 2
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    if turn.start <= mid <= turn.end:
                        seg["speaker"] = speaker
                        break
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
    
    def _summarize(self, text):
        key = os.getenv('GOOGLE_API_KEY')
        if not key:
            return None
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Return JSON {{'title':'','summary':'','tags':[]}} for: {text[:8000]}"
            resp = model.generate_content(prompt)
            return json.loads(resp.text.replace('```json', '').replace('```', ''))
        except Exception:
            return None

    # --- Helpers ---
    
    def _update(self, task_id, status, progress, message, **kwargs):
        with self.lock:
            self.tasks[task_id].update({'status': status, 'progress': progress, 'message': message, **kwargs})
        self._save_tasks()
    
    def _save_tasks(self):
        with open(TASKS_FILE, 'w') as f:
            json.dump(self.tasks, f)
    
    def _load_tasks(self):
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, 'r') as f:
                    self.tasks = json.load(f)
            except Exception:
                self.tasks = {}
    
    def _save_results(self, audio, segments, text):
        base = os.path.splitext(audio)[0]
        with open(f"{base}.txt", 'w', encoding='utf-8') as f:
            f.write(text)
        with open(f"{base}_segments.json", 'w', encoding='utf-8') as f:
            json.dump({'segments': segments}, f, ensure_ascii=False)
    
    def _cleanup_old_files(self):
        cutoff = time.time() - (CLEANUP_HOURS * 3600)
        if os.path.exists(DOWNLOAD_FOLDER):
            for f in os.listdir(DOWNLOAD_FOLDER):
                path = os.path.join(DOWNLOAD_FOLDER, f)
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
    
    def _check_idle(self):
        with self.lock:
            active = sum(1 for t in self.tasks.values() if t.get('status') not in ('completed', 'error'))
        if active == 0 and self.task_queue.qsize() == 0:
            if (time.time() - self.idle_start) / 60 >= self.idle_timeout:
                if os.getenv('SHUTDOWN_DRY_RUN', 'true').lower() != 'true':
                    os.system("shutdown -h now")
        else:
            self.idle_start = time.time()
    
    def _shutdown(self):
        self.scheduler.shutdown(wait=False)