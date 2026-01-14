FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the faster-whisper model to avoid downloading at runtime
# This saves ~1GB download on every cold start
RUN python3 -c "from faster_whisper import download_model; download_model('base')"

# Copy the rest of the application
COPY . .

# Expose the port (Gunicorn default)
EXPOSE 5000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run Gunicorn with 1 worker + 4 threads (shared state) and long timeout
# Using 1 worker because TranscriptionManager uses in-memory task state
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
