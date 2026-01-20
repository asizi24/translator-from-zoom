FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code & static files
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run with Gunicorn + Uvicorn worker
# CRITICAL: --timeout 3600 prevents Cloud Run from killing long Gemini requests
CMD exec gunicorn main:app \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8080} \
    --timeout 3600 \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
