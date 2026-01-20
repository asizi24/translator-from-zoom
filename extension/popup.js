// Configuration
const SERVER_URL = 'YOUR_CLOUD_RUN_URL_HERE'; // Replace with your actual Cloud Run URL

// DOM Elements
const analyzeBtn = document.getElementById('analyzeBtn');
const clearBtn = document.getElementById('clearBtn');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const errorEl = document.getElementById('error');

// State
let isProcessing = false;

// Event Listeners
analyzeBtn.addEventListener('click', analyzeRecording);
clearBtn.addEventListener('click', clearResults);

// Main Function
async function analyzeRecording() {
    if (isProcessing) return;

    try {
        isProcessing = true;
        analyzeBtn.disabled = true;
        hideError();
        hideResults();

        // Step 1: Get active tab
        updateStatus('מחפש הקלטה...', true);
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab.url.includes('zoom.us')) {
            throw new Error('אנא פתח דף הקלטת Zoom');
        }

        // Step 2: Inject content script to get video URL
        const [result] = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: getVideoSource
        });

        if (!result || !result.result) {
            throw new Error('לא נמצא סרטון בדף');
        }

        const videoUrl = result.result;

        // Step 3: Download audio
        updateStatus('מוריד אודיו...', true);
        const audioBlob = await fetchAudioBlob(videoUrl);

        // Step 4: Upload to server
        updateStatus('מעבד עם AI...', true);
        const response = await uploadToServer(audioBlob);

        // Step 5: Display results
        updateStatus('הושלם בהצלחה! ✓', false);
        displayResults(response);

    } catch (error) {
        console.error('Error:', error);
        updateStatus('שגיאה', false);
        showError(error.message);
    } finally {
        isProcessing = false;
        analyzeBtn.disabled = false;
    }
}

// Helper: Get video source from page
function getVideoSource() {
    const video = document.querySelector('video');
    const audio = document.querySelector('audio');

    if (video && video.src) {
        return video.src;
    }

    if (audio && audio.src) {
        return audio.src;
    }

    // Try to find source in video/audio elements
    const videoSource = document.querySelector('video source');
    const audioSource = document.querySelector('audio source');

    if (videoSource && videoSource.src) {
        return videoSource.src;
    }

    if (audioSource && audioSource.src) {
        return audioSource.src;
    }

    return null;
}

// Helper: Fetch audio as Blob
async function fetchAudioBlob(url) {
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error('כשל בהורדת האודיו');
    }

    return await response.blob();
}

// Helper: Upload to server
async function uploadToServer(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');

    const response = await fetch(`${SERVER_URL}/analyze`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'שגיאת שרת');
    }

    return await response.json();
}

// Helper: Display results
function displayResults(data) {
    const { summary, quiz } = data;

    let html = '';

    // Summary Section
    if (summary) {
        html += `
            <div class="summary">
                <h3>📝 סיכום</h3>
                <p>${summary}</p>
            </div>
        `;
    }

    // Quiz Section
    if (quiz && quiz.length > 0) {
        html += `
            <div class="quiz">
                <h3>❓ שאלות</h3>
        `;

        quiz.forEach((q, index) => {
            html += `
                <div class="question">
                    <div class="question-text">${index + 1}. ${q.question}</div>
                    <ul class="options">
            `;

            q.options.forEach((option, optIndex) => {
                const isCorrect = optIndex === q.correct;
                html += `<li class="${isCorrect ? 'correct' : ''}">${option}${isCorrect ? ' ✓' : ''}</li>`;
            });

            html += `
                    </ul>
                </div>
            `;
        });

        html += `</div>`;
    }

    resultsEl.innerHTML = html;
    showResults();
}

// Helper: Update status
function updateStatus(message, loading = false) {
    statusEl.textContent = message;
    statusEl.classList.toggle('loading', loading);
}

// Helper: Show/Hide results
function showResults() {
    resultsEl.classList.add('show');
}

function hideResults() {
    resultsEl.classList.remove('show');
    resultsEl.innerHTML = '';
}

// Helper: Show/Hide error
function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.add('show');
}

function hideError() {
    errorEl.classList.remove('show');
    errorEl.textContent = '';
}

// Clear results
function clearResults() {
    hideResults();
    hideError();
    updateStatus('מוכן לניתוח...', false);
}

// Load saved results on popup open (optional)
chrome.storage.local.get(['lastResults'], (data) => {
    if (data.lastResults) {
        displayResults(data.lastResults);
        updateStatus('תוצאות אחרונות', false);
    }
});
