# 🎙️ Flask Transcription App - מדריך התקנה

ברוכים הבאים לאפליקציית התמלול האוטומטית! המערכת מאפשרת להוריד סרטונים, לתמלל אותם באמצעות Whisper AI, ולקבל סיכומים ותובנות באמצעות Google Gemini.

לפני שמתחילים, ודאו שיש לכם **Python 3.10** ומעלה מותקן על המחשב.

---

## 🚀 שלב 1: התקנת FFmpeg (חובה)

המערכת דורשת את כלי ה-FFmpeg לצורך עיבוד קבצי אודיו ווידאו.

### עבור Windows:
1. פתחו את ה-PowerShell כמנהל (Administrator).
2. הריצו את הפקודה הבאה להתקנה דרך `winget`:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   *אם הפקודה לא מזוהה, ניתן להוריד ידנית מהאתר [ffmpeg.org](https://ffmpeg.org/download.html) ולהוסיף ל-PATH.*

### עבור Mac:
```bash
brew install ffmpeg
```

---

## 📥 שלב 2: הורדת הפרויקט

פתחו את הטרמינל / CMD והריצו:

```bash
git clone https://github.com/YOUR_USERNAME/zoom-to-text.git
cd zoom-to-text
```

*(או הורידו את הקבצים כ-ZIP וחלצו אותם לספריה במחשב)*

---

## 🛠️ שלב 3: יצירת סביבה וירטואלית (מומלץ)

כדי למנוע התנגשויות עם ספריות אחרות, מומלץ ליצור סביבה מבודדת:

**ב-Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**ב-Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 📦 שלב 4: התקנת הספריות הדרושות

הריצו את הפקודה הבאה כדי להתקין את כל מה שדרוש:

```bash
pip install -r requirements.txt
```

---

## 🔑 שלב 5: הגדרת מפתח Google Gemini

כדי לקבל סיכומים ותשובות מ-AI, יש להגדיר מפתח API.
1. קבלו מפתח בחינם כאן: [Google AI Studio](https://aistudio.google.com/app/apikey)
2. הגדירו אותו במערכת:

**ב-Windows (PowerShell):**
```powershell
$env:GOOGLE_API_KEY="הדביקו_כאן_את_המפתח_שלכם"
```

**ב-Mac/Linux:**
```bash
export GOOGLE_API_KEY="הדביקו_כאן_את_המפתח_שלכם"
```

---

## ✅ שלב 6: בדיקת תקינות המערכת

לפני שמריצים, הפרויקט כולל סקריפט בדיקה אוטומטי שמוודא שהכל מותקן כראוי. הריצו:

```bash
python verify_system.py
```

אם אתם רואים סימוני ✅ ירוקים - אתם מוכנים!

---

## ▶️ שלב 7: הרצת האפליקציה

כעת אפשר להפעיל את השרת:

```bash
python app.py
```

לאחר שהשרת עולה, פתחו את הדפדפן בכתובת:
👉 **http://localhost:5000**

---

## 🆘 פתרון בעיות נפוצות

**ש: אני מקבל שגיאה ש-FFmpeg לא נמצא.**
ת: ודאו שהתקנתם את FFmpeg והוא מוגדר במשתני הסביבה (PATH). נסו לסגור ולפתוח מחדש את הטרמינל.

**ש: ה-AI לא עובד / אין סיכום.**
ת: ודאו שהגדרתם את `GOOGLE_API_KEY` לפני הרצת האפליקציה.

**ש: ההורדה נכשלת.**
ת: ודאו שיש לכם חיבור אינטרנט יציב ושהתיקייה `downloads` קיימת (הסקריפט יוצר אותה אוטומטית).

---

בהצלחה! 🎉
