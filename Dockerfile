FROM python:3.10-slim

WORKDIR /app

# 1. Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy Application Code & Assets
# מעתיק את הקוד ואת התיקיות static/templates
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run FastAPI with Uvicorn
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
