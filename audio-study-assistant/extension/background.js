// Audio Study Assistant - Background Service Worker
// Automatically intercepts audio downloads and uploads to Cloud Run

// Configuration - UPDATE THIS TO YOUR CLOUD RUN URL
const CONFIG = {
    API_BASE_URL: "https://YOUR-CLOUD-RUN-URL.run.app",
    SUPPORTED_EXTENSIONS: ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.aac', '.mp4'],
    AUTO_UPLOAD_ENABLED: true
};

// Store for pending uploads
const pendingUploads = new Map();

// Listen for download events
chrome.downloads.onCreated.addListener(async (downloadItem) => {
    if (!CONFIG.AUTO_UPLOAD_ENABLED) return;

    const filename = downloadItem.filename || downloadItem.url;
    const extension = getFileExtension(filename);

    if (CONFIG.SUPPORTED_EXTENSIONS.includes(extension.toLowerCase())) {
        console.log('Audio file detected:', filename);

        // Store download info
        pendingUploads.set(downloadItem.id, {
            url: downloadItem.url,
            filename: downloadItem.filename,
            startTime: Date.now()
        });

        // Show notification
        showNotification('הורדה התחילה', `הקובץ ${getBasename(filename)} יועלה אוטומטית לניתוח`);
    }
});

// Listen for download completion
chrome.downloads.onChanged.addListener(async (delta) => {
    if (delta.state && delta.state.current === 'complete') {
        const downloadInfo = pendingUploads.get(delta.id);

        if (downloadInfo) {
            pendingUploads.delete(delta.id);

            // Get the completed download
            chrome.downloads.search({ id: delta.id }, async (downloads) => {
                if (downloads.length > 0) {
                    const download = downloads[0];
                    await processAudioFile(download.filename);
                }
            });
        }
    }
});

// Process and upload audio file
async function processAudioFile(filePath) {
    const filename = getBasename(filePath);

    try {
        showNotification('מעלה קובץ', `מעלה את ${filename} לשרת...`);

        // Read file and upload
        const response = await fetch(filePath);
        const blob = await response.blob();

        // Create form data
        const formData = new FormData();
        formData.append('file', blob, filename);

        // Upload to Cloud Run
        const uploadResponse = await fetch(`${CONFIG.API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.statusText}`);
        }

        const uploadData = await uploadResponse.json();
        const gsUri = uploadData.gs_uri;

        showNotification('מנתח הקלטה', 'הקובץ הועלה בהצלחה, מנתח עם AI...');

        // Analyze the audio
        const analyzeResponse = await fetch(`${CONFIG.API_BASE_URL}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gs_uri: gsUri })
        });

        if (!analyzeResponse.ok) {
            throw new Error(`Analysis failed: ${analyzeResponse.statusText}`);
        }

        const analyzeData = await analyzeResponse.json();

        // Store results and open results page
        await chrome.storage.local.set({
            latestResult: {
                filename: filename,
                summary: analyzeData.summary,
                quiz: analyzeData.quiz,
                timestamp: Date.now()
            }
        });

        // Open results page in new tab
        chrome.tabs.create({
            url: chrome.runtime.getURL('results.html')
        });

        showNotification('הניתוח הושלם!', `סיכום וחידון מוכנים עבור ${filename}`);

    } catch (error) {
        console.error('Error processing audio:', error);
        showNotification('שגיאה', `נכשל בעיבוד ${filename}: ${error.message}`);
    }
}

// Utility functions
function getFileExtension(filename) {
    const match = filename.match(/\.[^.]+$/);
    return match ? match[0] : '';
}

function getBasename(filepath) {
    return filepath.split(/[\\/]/).pop();
}

function showNotification(title, message) {
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: title,
        message: message
    });
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getConfig') {
        sendResponse(CONFIG);
    } else if (request.action === 'updateConfig') {
        Object.assign(CONFIG, request.config);
        chrome.storage.local.set({ config: CONFIG });
        sendResponse({ success: true });
    } else if (request.action === 'uploadFile') {
        uploadFileFromPopup(request.file, request.filename)
            .then(sendResponse)
            .catch(err => sendResponse({ error: err.message }));
        return true; // Keep channel open for async response
    }
});

// Upload file from popup (manual upload)
async function uploadFileFromPopup(fileData, filename) {
    try {
        // Convert base64 to blob
        const response = await fetch(fileData);
        const blob = await response.blob();

        const formData = new FormData();
        formData.append('file', blob, filename);

        // Upload
        const uploadResponse = await fetch(`${CONFIG.API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.statusText}`);
        }

        const uploadData = await uploadResponse.json();

        // Analyze
        const analyzeResponse = await fetch(`${CONFIG.API_BASE_URL}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gs_uri: uploadData.gs_uri })
        });

        if (!analyzeResponse.ok) {
            throw new Error(`Analysis failed: ${analyzeResponse.statusText}`);
        }

        const analyzeData = await analyzeResponse.json();

        // Store and open results
        await chrome.storage.local.set({
            latestResult: {
                filename: filename,
                summary: analyzeData.summary,
                quiz: analyzeData.quiz,
                timestamp: Date.now()
            }
        });

        chrome.tabs.create({
            url: chrome.runtime.getURL('results.html')
        });

        return { success: true };

    } catch (error) {
        throw error;
    }
}

// Load saved config on startup
chrome.storage.local.get(['config'], (result) => {
    if (result.config) {
        Object.assign(CONFIG, result.config);
    }
});
