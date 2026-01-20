# Audio Study Assistant - Chrome Extension

## 🎯 Overview

Chrome Extension (Manifest V3) that captures audio from Zoom recordings and sends it to your Cloud Run backend for AI-powered analysis.

## 📋 Setup Instructions

### 1. Get Your Cloud Run URL

First, check if your deployment is complete and get the URL:

```bash
gcloud run services describe audio-study-assistant --region=us-central1 --format="value(status.url)"
```

### 2. Configure the Extension

Open `popup.js` and update line 2:

```javascript
const SERVER_URL = 'YOUR_CLOUD_RUN_URL_HERE'; // Replace with actual URL
```

Example:

```javascript
const SERVER_URL = 'https://audio-study-assistant-xxxxx-uc.a.run.app';
```

### 3. Add Extension Icons (Optional)

The extension expects 3 icon sizes. You can:

- Create your own icons (16x16, 48x48, 128x128 PNG)
- Or remove the icon references from `manifest.json` if you want to test without icons

### 4. Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `extension` folder
5. The extension should appear in your toolbar

## 🚀 Usage

1. Navigate to a Zoom recording page (e.g., `https://zoom.us/rec/play/...`)
2. Click the extension icon in your toolbar
3. Click **"נתח הקלטה"** (Analyze Recording)
4. Wait for:
   - Audio download
   - AI processing
   - Results display
5. View the summary and quiz in Hebrew

## 🛠️ Files

| File | Purpose |
|------|---------|
| `manifest.json` | Extension configuration (Manifest V3) |
| `popup.html` | Modern Hebrew RTL interface |
| `popup.js` | Main logic: capture → upload → display |
| `content.js` | Injected script to find video/audio elements |

## 🔧 Troubleshooting

**"אנא פתח דף הקלטת Zoom"**

- Make sure you're on a Zoom recording page (`*.zoom.us/*`)

**"לא נמצא סרטון בדף"**

- The page might not have loaded completely
- Refresh the Zoom page and try again
- Check browser console for errors

**"שגיאת שרת"**

- Verify your `SERVER_URL` is correct
- Check that Cloud Run deployment is successful
- Ensure the service allows unauthenticated access

## 📝 Notes

- The extension stores the last result in `chrome.storage.local`
- Works only on `*.zoom.us` domains
- Requires active internet connection
- Audio files are sent to your Cloud Run backend for processing

## 🔒 Permissions

- `activeTab`: Access current tab content
- `scripting`: Inject scripts to find video elements
- `storage`: Save last results
- `*://*.zoom.us/*`: Access Zoom recording pages
- `*://*.run.app/*`: Communicate with Cloud Run backend
