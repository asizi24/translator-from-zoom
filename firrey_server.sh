#!/bin/bash

echo "🤖 הסוכן מתחיל בעבודה: תיקון והגדרת השרת..."

# 1. עדכון מערכת והתקנת FFmpeg (חובה לוידאו)
echo "🛠️ מתקין כלי מערכת (FFmpeg)..."
sudo apt update
sudo apt install -y ffmpeg python3-pip

# 2. וידוא התקנת ספריות Python
echo "📦 מתקין ספריות Python..."
pip3 install -r requirements.txt

# 3. סידור הרשאות (כדי למנוע שגיאות Permission denied)
echo "🔓 מסדר הרשאות לתיקיות הורדה..."
mkdir -p downloads uploads
sudo chown -R ubuntu:ubuntu .
chmod -R 777 downloads uploads

# 4. תיקון הבאג בקוד (TranscriptionManager) באופן אוטומטי
# הפקודה הזו מחפשת את השורה הבעייתית ב-app.py ומחליפה אותה בגרסה התקינה
echo "🐛 מתקן באגים בקוד..."
if grep -q "hf_token=config.HF_TOKEN" app.py; then
    sed -i 's/manager = TranscriptionManager(hf_token=config.HF_TOKEN)/manager = TranscriptionManager()/' app.py
    echo "✅ תוקן: הוסר הפרמטר המיותר hf_token"
else
    echo "✅ הקוד כבר תקין."
fi

# 5. עצירה והפעלה מחדש של האפליקציה
echo "🔄 מפעיל מחדש את המערכת..."
pkill -f gunicorn || true
pkill -f app.py || true
sleep 2

# Running with Gunicorn (production-grade WSGI server)
# -w 1: single worker (sufficient for transcription workload)
# --threads 4: 4 threads per worker for concurrent requests
# --timeout 300: 5 minute timeout for long transcriptions
echo "🚀 Starting Gunicorn server..."
nohup gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 --timeout 300 app:app > output.log 2>&1 &

echo "🎉 סיימתי! המערכת רצה ברקע עם Gunicorn."
echo "תוכל לראות את הלוגים עכשיו עם הפקודה: tail -f output.log"
