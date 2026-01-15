FROM python:3.10-slim

# 1. התקנת תלויות מערכת
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    libsndfile1 \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. PyTorch CPU-only (saves 3GB+ vs CUDA version)
RUN pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .

# 3. Install deps - CRITICAL: Install pyannote.audio without its torch dependency
#    Otherwise it will override CPU torch with 3GB CUDA version
RUN sed -i '/^torch/d' requirements.txt && \
    sed -i '/pyannote.audio/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps pyannote.audio && \
    pip install --no-cache-dir pyannote.core pyannote.database pyannote.pipeline pyannote.metrics asteroid-filterbanks einops lightning pytorch-metric-learning rich soundfile torchmetrics

# 4. Download Whisper model (large-v3 for maximum quality)
RUN python3 -c "from faster_whisper import download_model; download_model('large-v3')"

COPY . .

# 5. תיקון לקוד (Diarization Token Fix)
RUN sed -i 's/use_auth_token=self.hf_token/token=self.hf_token/g' transcriber_engine.py || true

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1200", "app:app"]
