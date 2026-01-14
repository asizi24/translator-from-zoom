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

# 2. טריק לחיסכון במקום: התקנת PyTorch בגרסת CPU בלבד (חוסך 3GB!)
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .

# 3. הסרת torch מהקובץ (כדי ש-pip לא ינסה לשדרג לגרסה הכבדה) והתקנת השאר
RUN sed -i '/torch/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# 4. הורדת מודל Whisper
RUN python3 -c "from faster_whisper import download_model; download_model('tiny')"

COPY . .

# 5. תיקון לקוד (Diarization Token Fix)
RUN sed -i 's/use_auth_token=self.hf_token/token=self.hf_token/g' transcriber_engine.py || true

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1200", "app:app"]
