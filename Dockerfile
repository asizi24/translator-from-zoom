# Use slim python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# FIX: Use Gunicorn with Uvicorn workers AND long timeout
# Cloud Run sets $PORT env var automatically
# --timeout 3600 gives Gemini 1 hour to process (plenty)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 3600 -k uvicorn.workers.UvicornWorker main:app
