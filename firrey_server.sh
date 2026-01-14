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
pkill -f app.py
sleep 2
nohup python3 app.py > output.log 2>&1 &

echo "🎉 סיימתי! המערכת רצה ברקע."
echo "תוכל לראות את הלוגים עכשיו עם הפקודה: tail -f output.log"
