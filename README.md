# Zoom Transcription App

## 🚀 גרסאות להורדה

פרויקט זה זמין בשתי תצורות, בהתאם לחומרה שברשותך:

### ☁️ גרסת הענן (מומלצת למחשבים סטנדרטיים)

* **נמצאת כאן (`main` branch).**
* **דרישות:** חיבור לאינטרנט, מפתח Google Cloud.
* **יתרונות:** עובדת מהר על כל מחשב, אין צורך בכרטיס מסך.

### 💻 גרסת ה-Pro הלוקאלית (לבעלי מחשבים חזקים)

* **עברו לבראנץ': `local-monolith`** (או [לחצו כאן להורדה](https://github.com/Start-Up-Nation-Cto/zoom-to-text/archive/refs/heads/local-monolith.zip)).
* **דרישות:** כרטיס מסך NVIDIA (מומלץ), 16GB RAM.
* **יתרונות:** פרטיות מלאה, עובד ללא אינטרנט, ללא עלויות ענן.

---

# 🎙️ Flask Transcription App

אפליקציית תמלול אוטומטית להקלטות Zoom ווידאו. מתמלל באמצעות **Whisper AI (Large-v3)**, מזהה דוברים עם **Pyannote**, ומייצר סיכומים עם **Google Gemini**.

---

## ⚡ Quick Start (הרצה לוקאלית - הכי מהיר!)

### Windows - בשני קליקים

1. **הורידו** את הפרויקט: `git clone https://github.com/asizi24/translator-from-zoom.git`
2. **לחצו פעמיים** על `install.bat` (התקנה חד-פעמית)
3. **לחצו פעמיים** על `start.bat` (הפעלה)

### כל מערכת הפעלה

```bash
git clone https://github.com/asizi24/translator-from-zoom.git
cd translator-from-zoom
pip install -r requirements.txt
python run_local.py
```

### 🎮 יש לכם כרטיס NVIDIA? (12x יותר מהיר!)

```bash
# התקינו PyTorch עם CUDA:
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

---

## 🐳 התקנה עם Docker (מומלץ)

### דרישות מקדימות

* [Docker](https://docs.docker.com/get-docker/) מותקן
* [Docker Compose](https://docs.docker.com/compose/install/) מותקן

### שלב 1: הורדת הפרויקט

```bash
git clone https://github.com/asizi24/translator-from-zoom.git
cd translator-from-zoom
```

### שלב 2: הגדרת משתני סביבה

צרו קובץ `.env` בתיקיית הפרויקט:

```bash
# .env
GOOGLE_API_KEY=your_google_api_key_here
HF_TOKEN=your_huggingface_token_here
```

**קבלת מפתחות:**

* Google API Key: [Google AI Studio](https://aistudio.google.com/app/apikey)
* HuggingFace Token (לזיהוי דוברים): [HuggingFace Settings](https://huggingface.co/settings/tokens)

### שלב 3: הרצה

```bash
docker-compose up -d
```

האפליקציה תהיה זמינה ב: **<http://localhost>** (פורט 80)

### פקודות שימושיות

```bash
# צפייה בלוגים
docker-compose logs -f

# עצירה
docker-compose down

# בנייה מחדש (לאחר עדכון קוד)
docker-compose build --no-cache && docker-compose up -d
```

---

## 🖥️ התקנה מקומית (ללא Docker)

<details>
<summary>לחצו להרחבה</summary>

### דרישות

* Python 3.10+
* FFmpeg

### התקנת FFmpeg

**Windows:**

```powershell
winget install Gyan.FFmpeg
```

**Mac:**

```bash
brew install ffmpeg
```

### התקנת הפרויקט

```bash
git clone https://github.com/asizi24/translator-from-zoom.git
cd translator-from-zoom

# סביבה וירטואלית
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# או: .venv\Scripts\activate  # Windows

# התקנת ספריות
pip install -r requirements.txt
```

### הגדרת מפתחות

```bash
export GOOGLE_API_KEY="your_key_here"
export HF_TOKEN="your_token_here"
```

### הרצה

```bash
python app.py
```

פתחו: **<http://localhost:5000>**

</details>

---

## ☁️ הפעלה ב-AWS EC2

<details>
<summary>לחצו להרחבה</summary>

### מפרט מומלץ

* **Instance Type:** `m7i-flex.large` או יותר (2 vCPUs, 8GB RAM)
* **Storage:** 30GB gp3
* **OS:** Ubuntu 22.04 LTS

### התקנה

```bash
# הורידו את סקריפט ההתקנה
curl -O https://raw.githubusercontent.com/asizi24/translator-from-zoom/main/scripts/ec2-setup.sh
chmod +x ec2-setup.sh
./ec2-setup.sh
```

### CI/CD

הפרויקט כולל GitHub Actions לדיפלוי אוטומטי. ראו `.github/workflows/deploy.yml`.

</details>

---

## 🆘 פתרון בעיות

| בעיה | פתרון |
|------|--------|
| FFmpeg לא נמצא | ודאו התקנה והוספה ל-PATH |
| AI לא עובד | בדקו שהגדרתם `GOOGLE_API_KEY` |
| אין זיהוי דוברים | ודאו `HF_TOKEN` ואישור מודל ב-HuggingFace |
| Docker permission denied | הריצו עם `sudo` או עשו logout/login |
| No space left on device | הריצו `docker system prune -af` |

---

## 📄 License

MIT

---

בהצלחה! 🎉
