# =============================================================================
# Dockerfile - Production-Grade Multi-Stage Build
# =============================================================================
# Features:
# - Multi-stage build for smaller image
# - CPU-optimized PyTorch (no CUDA bloat)
# - Configurable Whisper model via ARG
# - Non-root user for security
# - Optimized layer caching
#
# Author: DevSquad AI (Senior Tech Lead Rewrite)
# =============================================================================

# Stage 1: Builder - Install dependencies
FROM python:3.10-slim AS builder

# Build-time arguments
ARG WHISPER_MODEL=small

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install PyTorch CPU-only first (saves 3GB+ vs CUDA)
# Pre-install deps to avoid metadata issues with PyTorch CPU index
RUN pip install --no-cache-dir \
    typing-extensions sympy filelock networkx jinja2 fsspec

RUN pip install --no-cache-dir \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cpu \
    --no-deps

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install deps - Handle pyannote.audio separately to avoid CUDA torch override
RUN sed -i '/^torch/d' requirements.txt && \
    sed -i '/pyannote.audio/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps pyannote.audio && \
    pip install --no-cache-dir \
    pyannote.core pyannote.database pyannote.pipeline \
    pyannote.metrics asteroid-filterbanks einops lightning \
    pytorch-metric-learning rich soundfile torchmetrics

# Download Whisper model (cache in image for fast startup)
RUN python3 -c "from faster_whisper import download_model; download_model('${WHISPER_MODEL}')"

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.10-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Whisper model cache
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories with correct permissions
RUN mkdir -p downloads uploads && \
    chown -R appuser:appuser /app /home/appuser

# Switch to non-root user
USER appuser

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/appuser/.cache/huggingface

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run with Gunicorn
# - 1 worker (Whisper uses significant memory)
# - 4 threads for concurrent requests  
# - 1200s timeout for long transcriptions
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1200", "app:app"]
