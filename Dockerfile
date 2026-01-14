FROM python:3.10-slim

# 1. התקנת תלויות מערכת (הוספנו ספריות פיתוח כדי ש-av יצליח להתקין)
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

COPY requirements.txt .

# 2. שדרוג pip והתקנת הספריות (כולל זיהוי דוברים)
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# 3. הורדת המודל המהיר מראש
RUN python3 -c "from faster_whisper import download_model; download_model('tiny')"

COPY . .

EXPOSE 5000

# 4. הפעלה עם זמן קצוב ארוך (20 דקות) למניעת ניתוקים בהקלטות ארוכות
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1200", "app:app"]
