FROM python:3.10-slim

# התקנת תלויות מערכת (הוספנו את libsndfile1 לזיהוי דוברים)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# העתקת דרישות והתקנה
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# הורדת המודל המהיר מראש (Tiny במקום Base)
RUN python3 -c "from faster_whisper import download_model; download_model('tiny')"

COPY . .

EXPOSE 5000

# שימוש ב-Gunicorn עם זמן קצוב ארוך מאוד (כי תמלול לוקח זמן)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1200", "app:app"]
