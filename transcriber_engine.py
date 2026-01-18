"""
Transcription Engine - Production-Grade Implementation.

Features:
- Thread-safe task queue with proper lock management
- Configurable Whisper model via environment
- Graceful error handling with specific exceptions
- Real-time progress updates
- Optional speaker diarization
- Automatic file cleanup

Author: DevSquad AI (Senior Tech Lead Rewrite)
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from typing import Any, Dict, List, Optional, Tuple

import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from faster_whisper import WhisperModel
import google.generativeai as genai

# Conditional imports for optional features
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    Pipeline = None  # type: ignore
    PYANNOTE_AVAILABLE = False

try:
    import torch
except ImportError:
    torch = None  # type: ignore

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION - Environment-driven settings
# =============================================================================
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "large-v3")
DEFAULT_LANGUAGE: str = os.getenv("TRANSCRIPTION_LANGUAGE", "he")
DOWNLOAD_FOLDER: str = os.getenv("DOWNLOAD_FOLDER", "downloads")
UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "uploads")
TASKS_FILE: str = os.getenv("TASKS_FILE", "tasks_state.json")
CLEANUP_HOURS: int = int(os.getenv("CLEANUP_HOURS", "24"))

# =============================================================================
# GEMINI AI CONFIGURATION - GCP Optimized
# =============================================================================
GEMINI_MODEL_PRIMARY: str = "gemini-1.5-pro-latest"  # Massive 1M token context
GEMINI_MODEL_FALLBACK: str = "gemini-1.5-flash"       # Fallback on quota exceeded
GEMINI_MAX_TEXT_CHARS: int = 30000                     # Pro can handle much more

# Relaxed safety settings - don't block normal conversation transcripts
GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]

# Type aliases
TaskDict = Dict[str, Any]
SegmentDict = Dict[str, Any]


class TranscriptionError(Exception):
    """Base exception for transcription errors."""
    pass


class DownloadError(TranscriptionError):
    """Error during media download."""
    pass


class ModelError(TranscriptionError):
    """Error with AI model initialization or inference."""
    pass


class TranscriptionManager:
    """
    Production-grade background worker for transcription tasks.
    
    Thread-safe task queue manager with support for:
    - URL downloads via yt-dlp
    - Local file processing
    - Speaker diarization (optional)
    - AI summarization (optional)
    
    Senior Dev Note:
        Lock scope is minimized to prevent deadlocks. File I/O
        happens OUTSIDE the lock to avoid blocking the worker.
    """

    def __init__(
        self,
        test_mode: bool = False,
        hf_token: Optional[str] = None
    ) -> None:
        """
        Initialize the transcription manager.

        Args:
            test_mode: If True, use mock transcription for testing.
            hf_token: HuggingFace token for speaker diarization.
        """
        self.task_queue: queue.Queue[Tuple[str, Optional[str], Optional[str], Optional[bool]]] = queue.Queue()
        self._tasks: Dict[str, TaskDict] = {}
        self._lock = threading.RLock()  # RLock for nested locking safety
        self._test_mode = test_mode
        self._hf_token = hf_token or os.getenv("HF_TOKEN")
        
        # AI Models (lazy loaded)
        self._model: Optional[WhisperModel] = None
        self._diarization_pipeline: Optional[Any] = None

        # Auto-shutdown config (for cloud deployments)
        self._idle_start = time.time()
        self._idle_timeout_minutes = int(os.getenv("IDLE_TIMEOUT_MINUTES", "15"))
        self._auto_shutdown = os.getenv("AUTO_SHUTDOWN", "false").lower() == "true"
        self._scheduler: Optional[BackgroundScheduler] = None

        # Initialization
        self._load_tasks()
        self._reset_zombie_tasks()

        if not test_mode:
            self._init_models()

        self._start_background_services()
        atexit.register(self._shutdown)

    # =========================================================================
    # Model Initialization
    # =========================================================================

    def _init_models(self) -> None:
        """Initialize Whisper and diarization models."""
        self._init_whisper()
        self._init_diarization()

    def _init_whisper(self) -> None:
        """
        Initialize Whisper model with optimal settings for current hardware.
        
        Senior Dev Note:
            GPU detection happens at startup. For CPU, we use int8 quantization
            which reduces memory by 4x with minimal quality loss.
        """
        use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
        cpu_threads = int(os.getenv("CPU_THREADS", str(os.cpu_count() or 4)))

        if torch is not None and torch.cuda.is_available() and use_gpu:
            device, compute_type = "cuda", "float16"
            logger.info("GPU detected: %s", torch.cuda.get_device_name(0))
        else:
            device, compute_type = "cpu", "int8"
            logger.info("Using CPU with %d threads", cpu_threads)

        logger.info("Loading Whisper model '%s' on %s...", WHISPER_MODEL, device)

        try:
            if device == "cuda":
                self._model = WhisperModel(
                    WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type
                )
            else:
                self._model = WhisperModel(
                    WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=cpu_threads
                )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error("Failed to load Whisper model: %s", e)
            raise ModelError(f"Whisper initialization failed: {e}") from e

    def _init_diarization(self) -> None:
        """Initialize speaker diarization if HF token is provided."""
        if not self._hf_token or not PYANNOTE_AVAILABLE:
            logger.info("Diarization disabled (no HF token or pyannote unavailable)")
            return

        try:
            self._diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=self._hf_token
            )
            # Force CPU to avoid CUDA conflicts with Whisper
            if torch is not None:
                self._diarization_pipeline.to(torch.device("cpu"))
            logger.info("Speaker diarization initialized")
        except Exception as e:
            logger.warning("Diarization unavailable: %s", e)
            self._diarization_pipeline = None

    def _reset_zombie_tasks(self) -> None:
        """
        Mark any tasks that were in-progress when server crashed as errors.
        
        Senior Dev Note:
            This runs on startup BEFORE the worker thread starts, so no
            lock is strictly needed, but we use it for consistency.
        """
        zombie_statuses = {"downloading", "transcribing", "analyzing", "queued"}
        with self._lock:
            for task_id, task in self._tasks.items():
                if task.get("status") in zombie_statuses:
                    task.update({
                        "status": "error",
                        "message": "Server restarted during processing",
                        "progress": 0
                    })
                    logger.warning("Reset zombie task: %s", task_id)
        self._persist_tasks()

    def _start_background_services(self) -> None:
        """Start worker thread and scheduled jobs."""
        # Worker thread
        worker = threading.Thread(target=self._worker_loop, daemon=True, name="transcription-worker")
        worker.start()
        logger.info("Worker thread started")

        # Scheduler for cleanup and idle monitoring
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self._cleanup_old_files,
            "interval",
            hours=1,
            id="cleanup"
        )
        if self._auto_shutdown:
            self._scheduler.add_job(
                self._check_idle,
                "interval",
                minutes=1,
                id="idle_check"
            )
        self._scheduler.start()

    # =========================================================================
    # Public API
    # =========================================================================

    def submit_task(
        self,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        test_mode: Optional[bool] = None
    ) -> str:
        """
        Submit a new transcription task.

        Args:
            url: URL to download media from (YouTube, Zoom, etc.)
            file_path: Local file path to process
            test_mode: Override instance test mode for this task

        Returns:
            task_id: Unique identifier for tracking the task
        """
        task_id = str(uuid.uuid4())
        task_data: TaskDict = {
            "status": "queued",
            "progress": 0,
            "message": "Waiting in queue...",
            "created_at": time.time(),
            "url": url,
            "filename": None,
        }

        with self._lock:
            self._tasks[task_id] = task_data

        self._persist_tasks()
        self.task_queue.put((task_id, url, file_path, test_mode))
        logger.info("Task submitted: %s", task_id)

        return task_id

    def get_status(self, task_id: str) -> Optional[TaskDict]:
        """Get current status of a task."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, TaskDict]:
        """Get a copy of all tasks."""
        with self._lock:
            return dict(self._tasks)

    @property
    def task_queue(self) -> queue.Queue:
        """Access to the task queue for monitoring."""
        return self._task_queue

    @task_queue.setter
    def task_queue(self, value: queue.Queue) -> None:
        self._task_queue = value

    @property
    def tasks(self) -> Dict[str, TaskDict]:
        """Read-only property for backwards compatibility."""
        return self._tasks

    # =========================================================================
    # Worker Thread
    # =========================================================================

    def _worker_loop(self) -> None:
        """
        Main worker loop - processes tasks from queue.
        
        Senior Dev Note:
            This runs in a daemon thread. We catch ALL exceptions to prevent
            the worker from dying. Each task is isolated.
        """
        while True:
            try:
                task_data = self.task_queue.get()
                task_id, url, file_path, test_mode = task_data

                try:
                    self._process_task(task_id, url, file_path, test_mode)
                except TranscriptionError as e:
                    logger.error("Task %s failed: %s", task_id, e)
                    self._update_task(task_id, "error", 0, str(e))
                except Exception as e:
                    logger.exception("Unexpected error in task %s", task_id)
                    self._update_task(task_id, "error", 0, f"Unexpected error: {e}")
                finally:
                    self.task_queue.task_done()

            except Exception as e:
                logger.exception("Critical error in worker loop: %s", e)
                time.sleep(1)  # Prevent tight loop on repeated errors

    def _process_task(
        self,
        task_id: str,
        url: Optional[str],
        file_path: Optional[str],
        test_mode: Optional[bool]
    ) -> None:
        """Process a single transcription task."""
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

        # Test mode for UI verification
        if test_mode or self._test_mode:
            self._run_test_flow(task_id)
            return

        # Step 1: Download/locate audio
        audio_path = self._download_audio(task_id, url, file_path)

        # Step 2: Transcribe
        segments, full_text = self._transcribe_audio(task_id, audio_path)

        # Step 3: Speaker diarization (optional)
        if self._diarization_pipeline:
            self._apply_diarization(task_id, audio_path, segments)

        # Step 4: AI Summary (optional)
        self._update_task(task_id, "analyzing", 90, "Generating AI summary...")
        summary = self._generate_summary(full_text)

        # Step 5: Save results
        self._save_results(audio_path, segments, full_text)

        # Step 6: Cleanup downloaded files (keep uploads)
        output_filename = audio_path.replace(".wav", ".txt")
        self._update_task(
            task_id, "completed", 100, "Done!",
            filename=output_filename,
            text=full_text,
            transcript_text=full_text,
            transcript_segments=segments,
            summary=summary,
            segments=segments
        )

        # Remove temp audio if it was downloaded (not uploaded)
        if url and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError as e:
                logger.warning("Could not remove temp audio: %s", e)

    def _run_test_flow(self, task_id: str) -> None:
        """Simulated transcription for testing."""
        self._update_task(task_id, "downloading", 10, "[TEST] Simulating download...")
        time.sleep(0.3)
        self._update_task(task_id, "transcribing", 50, "[TEST] Simulating transcription...")
        time.sleep(0.3)
        self._update_task(
            task_id, "completed", 100, "[TEST] Complete!",
            filename="test_output.txt",
            text="This is a test transcript.",
            transcript_text="This is a test transcript.",
            summary={"title": "Test", "summary": "Test summary", "tags": ["test"]},
            segments=[{"start": 0, "end": 1, "text": "Test segment", "speaker": "A"}],
            transcript_segments=[{"start": 0, "end": 1, "text": "Test segment", "speaker": "A"}]
        )

    # =========================================================================
    # Processing Steps
    # =========================================================================

    def _download_audio(
        self,
        task_id: str,
        url: Optional[str],
        file_path: Optional[str]
    ) -> str:
        """Download or locate audio file."""
        self._update_task(task_id, "downloading", 10, "Preparing audio...")

        if file_path:
            logger.info("Using provided file: %s", file_path)
            return file_path

        if not url:
            raise DownloadError("No URL or file path provided")

        self._update_task(task_id, "downloading", 15, "Downloading from URL...")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav"
            }],
            "postprocessor_args": ["-ar", "16000", "-ac", "1"],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".wav"
                logger.info("Downloaded audio: %s", audio_path)
                return audio_path
        except Exception as e:
            raise DownloadError(f"Download failed: {e}") from e

    def _transcribe_audio(
        self,
        task_id: str,
        audio_path: str
    ) -> Tuple[List[SegmentDict], str]:
        """
        Transcribe audio with real-time progress updates.
        
        Senior Dev Note:
            We use beam_size=1 for speed. For higher quality, use beam_size=5.
            VAD filter removes silence, saving ~30% processing time.
        """
        if self._model is None:
            raise ModelError("Whisper model not initialized")

        self._update_task(task_id, "transcribing", 25, "Starting transcription...")

        # Get audio duration for progress calculation
        duration = self._get_audio_duration(audio_path)

        # Transcribe with optimized parameters
        segments_gen, _ = self._model.transcribe(
            audio_path,
            beam_size=1,  # Speed: 1, Quality: 5
            language=DEFAULT_LANGUAGE,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            no_speech_threshold=0.7,
            compression_ratio_threshold=3.0,
            log_prob_threshold=-1.5,
            word_timestamps=False,  # Skip for speed
            condition_on_previous_text=False,  # Faster, less context
        )

        segments: List[SegmentDict] = []
        text_parts: List[str] = []
        last_progress_time = 0.0

        try:
            for seg in segments_gen:
                # Format timestamp as [HH:MM:SS] for precise time reference
                timestamp_formatted = self._format_timestamp(seg.start)
                segment_data: SegmentDict = {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                    "speaker": "UNKNOWN",
                    "timestamp_formatted": timestamp_formatted
                }
                segments.append(segment_data)
                text_parts.append(seg.text)

                # Update progress every 30s of audio
                if duration > 0 and seg.end - last_progress_time > 30:
                    progress = min(25 + int((seg.end / duration) * 55), 80)
                    time_str = self._format_timestamp(seg.end)
                    duration_str = self._format_timestamp(duration)
                    self._update_task(
                        task_id, "transcribing", progress,
                        f"Transcribing... {time_str} / {duration_str}"
                    )
                    last_progress_time = seg.end
        except Exception as e:
            # Handle corrupted audio segments gracefully
            logger.warning("Error during transcription (partial results saved): %s", e)
            if not segments:
                raise TranscriptionError(f"Audio transcription failed: {e}") from e
            # Continue with partial results if we have some segments

        full_text = " ".join(text_parts).strip()
        logger.info("Transcribed %d segments, %d chars", len(segments), len(full_text))

        return segments, full_text

    def _apply_diarization(
        self,
        task_id: str,
        audio_path: str,
        segments: List[SegmentDict]
    ) -> None:
        """Apply speaker diarization to segments."""
        if not self._diarization_pipeline:
            return

        self._update_task(task_id, "transcribing", 82, "Identifying speakers...")

        try:
            diarization = self._diarization_pipeline(audio_path)

            for seg in segments:
                midpoint = (seg["start"] + seg["end"]) / 2
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    if turn.start <= midpoint <= turn.end:
                        seg["speaker"] = speaker
                        break

            speaker_count = len(set(s["speaker"] for s in segments if s["speaker"] != "UNKNOWN"))
            logger.info("Identified %d speakers", speaker_count)

        except Exception as e:
            logger.warning("Diarization failed, continuing without: %s", e)

    def _generate_summary(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Generate AI summary using Google Gemini (Pro with Flash fallback).
        
        GCP Optimized Features:
        - Uses Gemini 1.5 Pro with massive 1M token context window
        - Auto-fallback to Flash if Pro quota exceeded
        - Relaxed safety settings for transcript content
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        # Skip if text is too short
        if len(text.strip()) < 100:
            return {"title": "תמלול קצר", "summary": "התמלול קצר מדי לסיכום.", "tags": []}

        genai.configure(api_key=api_key)
        
        # Powerhouse Prompt - Professor Level analysis
        text_to_analyze = text[:GEMINI_MAX_TEXT_CHARS]
        prompt = f"""אתה עוזר לימודים מומחה (Professor Level). נתח את התמלול הבא של שיעור.
החזר JSON בלבד עם השדות: title, summary (סיכום מעמיק), key_points (נקודות מפתח), tags.

כללים:
- הכל בעברית
- התמקד בתוכן הלימודי
- אם יש קוד או מושגים טכניים, כלול אותם
- אם התמלול לא ברור, סכם את מה שניתן להבין

תמלול השיעור:
{text_to_analyze}"""

        try:
            # 1. Try the Beast: Gemini 1.5 Pro
            logger.info("Attempting summary with Gemini 1.5 Pro...")
            model = genai.GenerativeModel(
                GEMINI_MODEL_PRIMARY,
                safety_settings=GEMINI_SAFETY_SETTINGS
            )
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3}
            )
            result = self._parse_json_response(response.text)
            result["model_used"] = GEMINI_MODEL_PRIMARY
            logger.info("Summary generated using %s", GEMINI_MODEL_PRIMARY)
            return result

        except Exception as e:
            error_msg = str(e)
            # Check for Quota/Resource Exhausted
            if "429" in error_msg or "ResourceExhausted" in error_msg or "Quota" in error_msg:
                logger.warning("⚠️ Quota exceeded for Pro model. Falling back to Flash...")
                try:
                    # 2. Fallback to the Workhorse: Gemini 1.5 Flash
                    model = genai.GenerativeModel(
                        GEMINI_MODEL_FALLBACK,
                        safety_settings=GEMINI_SAFETY_SETTINGS
                    )
                    response = model.generate_content(
                        prompt,
                        generation_config={"temperature": 0.3}
                    )
                    result = self._parse_json_response(response.text)
                    result["model_used"] = GEMINI_MODEL_FALLBACK
                    logger.info("Summary generated using fallback %s", GEMINI_MODEL_FALLBACK)
                    return result
                except Exception as flash_error:
                    logger.error("Flash fallback failed: %s", flash_error)
                    return self._error_summary(str(flash_error))
            else:
                logger.error("AI Summary failed: %s", e)
                return self._error_summary(str(e))

    def _parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """Helper to clean and parse JSON from AI response."""
        try:
            clean_text = raw_text.strip()
            # Remove markdown code blocks if present
            if clean_text.startswith("```"):
                clean_text = clean_text.split("```")[1]
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:]
                clean_text = clean_text.strip()
            
            result = json.loads(clean_text)
            # Ensure required fields exist
            result.setdefault("title", "שיעור")
            result.setdefault("summary", "")
            result.setdefault("key_points", [])
            result.setdefault("tags", [])
            return result
        except json.JSONDecodeError as e:
            logger.warning("Could not parse AI response as JSON: %s", e)
            return self._error_summary("JSON Parse Error")

    def _error_summary(self, error: str) -> Dict[str, Any]:
        """Return a standardized error summary dict."""
        return {
            "title": "שגיאה בסיכום",
            "summary": f"לא ניתן היה לייצר סיכום עקב תקלה: {error[:100]}",
            "key_points": [],
            "tags": ["error"],
            "error": error
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """
        Format seconds as [HH:MM:SS] for precise time reference.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted string like "[00:05:23]"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds."""
        try:
            with wave.open(audio_path, "rb") as w:
                framerate = w.getframerate()
                if framerate == 0:
                    return 0.0
                return w.getnframes() / framerate
        except wave.Error as e:
            logger.warning("Could not read WAV file: %s", e)
            return 0.0
        except Exception:
            return 0.0

    def _update_task(
        self,
        task_id: str,
        status: str,
        progress: int,
        message: str,
        **kwargs: Any
    ) -> None:
        """
        Update task status thread-safely.
        
        Senior Dev Note:
            Lock scope is minimal - we just update the dict. File I/O
            happens outside the lock via _persist_tasks().
        """
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update({
                    "status": status,
                    "progress": progress,
                    "message": message,
                    **kwargs
                })

        # Persist outside lock to avoid blocking
        self._persist_tasks()

    def _persist_tasks(self) -> None:
        """
        Atomically save tasks to disk.
        
        Senior Dev Note:
            We write to a temp file first, then rename. This prevents
            corrupted JSON if the process crashes during write.
        """
        try:
            with self._lock:
                data = dict(self._tasks)

            # Atomic write pattern
            fd, temp_path = tempfile.mkstemp(suffix=".json", dir=".")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                shutil.move(temp_path, TASKS_FILE)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except Exception as e:
            logger.error("Failed to persist tasks: %s", e)

    def _load_tasks(self) -> None:
        """Load tasks from disk on startup."""
        if not os.path.exists(TASKS_FILE):
            return

        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                self._tasks = json.load(f)
            logger.info("Loaded %d tasks from disk", len(self._tasks))
        except json.JSONDecodeError as e:
            logger.error("Corrupted tasks file, starting fresh: %s", e)
            self._tasks = {}
        except Exception as e:
            logger.error("Could not load tasks: %s", e)
            self._tasks = {}

    def _save_results(
        self,
        audio_path: str,
        segments: List[SegmentDict],
        text: str
    ) -> None:
        """
        Save transcription results to files with precise timestamps.
        
        Output formats:
        - .txt: Plain text with [HH:MM:SS] timestamps per segment
        - _segments.json: Full segment data with speaker/timing info
        """
        base = os.path.splitext(audio_path)[0]

        # Plain text transcript with timestamps
        with open(f"{base}.txt", "w", encoding="utf-8") as f:
            for seg in segments:
                timestamp = seg.get("timestamp_formatted", self._format_timestamp(seg.get("start", 0)))
                speaker = seg.get("speaker", "UNKNOWN")
                text_line = seg.get("text", "").strip()
                if text_line:
                    f.write(f"{timestamp} {speaker}: {text_line}\n")

        # Segments with timing/speaker info (JSON for programmatic access)
        with open(f"{base}_segments.json", "w", encoding="utf-8") as f:
            json.dump({"segments": segments}, f, ensure_ascii=False, indent=2)

    def _cleanup_old_files(self) -> None:
        """Remove files older than CLEANUP_HOURS from downloads and uploads."""
        cutoff = time.time() - (CLEANUP_HOURS * 3600)

        for folder in [DOWNLOAD_FOLDER, UPLOAD_FOLDER]:
            if not os.path.exists(folder):
                continue

            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    try:
                        if os.path.getmtime(filepath) < cutoff:
                            os.remove(filepath)
                            logger.info("Cleaned up old file: %s", filepath)
                    except OSError as e:
                        logger.warning("Could not remove %s: %s", filepath, e)

    def _check_idle(self) -> None:
        """Check for idle timeout and trigger shutdown if needed."""
        with self._lock:
            active = sum(
                1 for t in self._tasks.values()
                if t.get("status") not in ("completed", "error")
            )

        queue_empty = self.task_queue.qsize() == 0

        if active == 0 and queue_empty:
            idle_minutes = (time.time() - self._idle_start) / 60
            if idle_minutes >= self._idle_timeout_minutes:
                dry_run = os.getenv("SHUTDOWN_DRY_RUN", "true").lower() == "true"
                if dry_run:
                    logger.info("IDLE SHUTDOWN (dry run): Would shutdown now")
                else:
                    logger.warning("Idle timeout reached, initiating shutdown...")
                    subprocess.run(["shutdown", "-h", "now"], check=False)
        else:
            self._idle_start = time.time()

    def _shutdown(self) -> None:
        """Clean shutdown of background services."""
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass