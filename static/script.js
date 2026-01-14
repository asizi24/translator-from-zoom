// Global state
let currentTaskId = null;
let pollInterval = null;
let selectedFile = null;

// Paste from clipboard
async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        document.getElementById('zoom-url').value = text;
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        alert('לא ניתן לגשת ללוח. אנא הדבק ידנית.');
    }
}

// Tab switching
function switchTab(tab) {
    const urlTab = document.getElementById('url-tab');
    const uploadTab = document.getElementById('upload-tab');
    const urlContent = document.getElementById('url-content');
    const uploadContent = document.getElementById('upload-content');

    if (tab === 'url') {
        urlTab.className = 'flex-1 py-3 px-4 text-center font-medium border-b-2 border-purple-600 text-purple-600 transition';
        uploadTab.className = 'flex-1 py-3 px-4 text-center font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700 transition';
        urlContent.classList.remove('hidden');
        uploadContent.classList.add('hidden');
    } else {
        uploadTab.className = 'flex-1 py-3 px-4 text-center font-medium border-b-2 border-purple-600 text-purple-600 transition';
        urlTab.className = 'flex-1 py-3 px-4 text-center font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700 transition';
        uploadContent.classList.remove('hidden');
        urlContent.classList.add('hidden');
    }
}

// File upload handlers
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelection(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        handleFileSelection(files[0]);
    }
}

function handleFileSelection(file) {
    selectedFile = file;

    // Display file info
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-size').textContent = formatFileSize(file.size);
    document.getElementById('selected-file').classList.remove('hidden');
    document.getElementById('upload-btn').disabled = false;
}

function clearFileSelection() {
    selectedFile = null;
    document.getElementById('selected-file').classList.add('hidden');
    document.getElementById('file-input').value = '';
    document.getElementById('upload-btn').disabled = true;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function uploadFile() {
    if (!selectedFile) {
        showError('אנא בחר קובץ');
        return;
    }

    const uploadBtn = document.getElementById('upload-btn');
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = 'מעלה...';

    const formData = new FormData();
    formData.append('file', selectedFile);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = 'התחל תמלול מהקובץ';
            } else {
                // Success - got task_id
                currentTaskId = data.task_id;
                localStorage.setItem('currentTaskId', currentTaskId);

                // Switch to progress view
                document.getElementById('input-section').classList.add('hidden');
                document.getElementById('progress-section').classList.remove('hidden');
                addLog('מעבד קובץ...');

                // Start polling
                pollInterval = setInterval(() => checkStatus(currentTaskId), 1000);
            }
        })
        .catch(error => {
            showError('שגיאה בהעלאת הקובץ');
            console.error('Error:', error);
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = 'התחל תמלול מהקובץ';
        });
}

// On page load
window.addEventListener('DOMContentLoaded', () => {
    // Check if there's a saved task in progress
    const savedTaskId = localStorage.getItem('currentTaskId');
    if (savedTaskId) {
        currentTaskId = savedTaskId;
        resumeTask(savedTaskId);
    }

    // Load history
    loadHistory();
});

function startProcessURL() {
    const urlInput = document.getElementById('zoom-url');
    const url = urlInput.value.trim();
    const errorMsg = document.getElementById('error-msg');
    const startBtn = document.getElementById('start-btn');

    // Validation
    if (!url) {
        showError('אנא הכנס קישור תקין');
        return;
    }

    // Reset UI
    errorMsg.classList.add('hidden');
    startBtn.disabled = true;
    startBtn.classList.add('opacity-50', 'cursor-not-allowed');
    startBtn.innerHTML = 'מתחיל...';

    // API Call
    fetch('/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: url }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
                resetBtn();
            } else {
                // Success - got task_id
                currentTaskId = data.task_id;
                localStorage.setItem('currentTaskId', currentTaskId);

                // Switch to progress view
                document.getElementById('input-section').classList.add('hidden');
                document.getElementById('progress-section').classList.remove('hidden');
                addLog('מתחיל תהליך עיבוד...');

                // Start polling
                pollInterval = setInterval(() => checkStatus(currentTaskId), 1000);
            }
        })
        .catch(error => {
            showError('שגיאה בתקשורת עם השרת');
            console.error('Error:', error);
            resetBtn();
        });
}

function resumeTask(taskId) {
    // Resume monitoring an existing task
    document.getElementById('input-section').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    addLog('ממשיך משימה קודמת...');

    pollInterval = setInterval(() => checkStatus(taskId), 1000);
}

function checkStatus(taskId) {
    fetch(`/status/${taskId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                clearInterval(pollInterval);
                showErrorInLog(data.error);
                return;
            }

            updateProgress(data);

            if (data.status === 'completed') {
                clearInterval(pollInterval);
                localStorage.removeItem('currentTaskId');
                showCompletion(data);
                loadHistory(); // Refresh history
            } else if (data.status === 'error') {
                clearInterval(pollInterval);
                localStorage.removeItem('currentTaskId');
                showErrorInLog(data.message || data.error);
            }
        })
        .catch(error => console.error('Error polling status:', error));
}

function updateProgress(data) {
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const statusText = document.getElementById('status-text');

    const progress = data.progress || 0;
    progressBar.style.width = progress + '%';
    progressPercent.innerText = progress + '%';
    statusText.innerText = data.message || 'מעבד...';

    // Update morphing SVG loader
    if (window.updateMorphingLoader) {
        window.updateMorphingLoader(progress, data.message);
    }

    // Update progress bar color based on phase
    if (progress < 40) {
        // Download phase - blue
        progressBar.className = 'bg-blue-600 h-3 rounded-full transition-all duration-500';
    } else if (progress < 60) {
        // Audio extraction - purple
        progressBar.className = 'bg-purple-600 h-3 rounded-full transition-all duration-500';
    } else if (progress < 95) {
        // Transcription - green
        progressBar.className = 'bg-green-600 h-3 rounded-full transition-all duration-500';
    } else {
        // Finalizing - gold
        progressBar.className = 'bg-yellow-500 h-3 rounded-full transition-all duration-500';
    }
}

function addLog(message) {
    const console = document.getElementById('log-console');
    const div = document.createElement('div');
    div.innerText = `> ${message}`;
    console.appendChild(div);
    console.scrollTop = console.scrollHeight;
}

function showErrorInLog(msg) {
    const console = document.getElementById('log-console');
    const div = document.createElement('div');
    div.classList.add('text-red-500', 'font-bold');
    div.innerText = `> שגיאה: ${msg}`;
    console.appendChild(div);
    console.scrollTop = console.scrollHeight;
}

function showCompletion(taskData) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('completion-section').classList.remove('hidden');

    // Update download link with task_id (updated API)
    const downloadLink = document.getElementById('download-link');
    downloadLink.href = `/download/${currentTaskId}`;

    // Update preview download link
    const previewDownloadLink = document.getElementById('preview-download-link');
    previewDownloadLink.href = `/download/${currentTaskId}`;

    // Display AI Summary if available
    if (taskData.ai_summary) {
        displayAISummary(taskData.ai_summary);
    }
}

function displayAISummary(aiSummary) {
    const card = document.getElementById('ai-summary-card');
    const titleEl = document.getElementById('ai-title');
    const tagsEl = document.getElementById('ai-tags');
    const summaryEl = document.getElementById('ai-summary');

    if (!card || !aiSummary) return;

    // Set content
    titleEl.textContent = aiSummary.title || 'תמלול הושלם';
    summaryEl.textContent = aiSummary.summary || '';

    // Add tags
    tagsEl.innerHTML = '';
    if (aiSummary.tags && Array.isArray(aiSummary.tags)) {
        aiSummary.tags.forEach(tag => {
            const tagSpan = document.createElement('span');
            tagSpan.className = 'bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm font-medium';
            tagSpan.textContent = tag;
            tagsEl.appendChild(tagSpan);
        });
    }

    // Show card
    card.classList.remove('hidden');

    // Staggered reveal animation
    if (window.staggerRevealGSAP) {
        window.staggerRevealGSAP('.reveal-target', {
            duration: 0.6,
            stagger: 0.15,
            y: 20,
            opacity: 0
        });
    }
}

function resetUI() {
    document.getElementById('completion-section').classList.add('hidden');
    document.getElementById('input-section').classList.remove('hidden');
    document.getElementById('zoom-url').value = '';
    clearFileSelection();
    resetBtn();

    // Reset progress bars
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-percent').innerText = '0%';
    document.getElementById('log-console').innerHTML = '<div class="opacity-50">> המערכת מוכנה.</div>';

    currentTaskId = null;
}

function showError(msg) {
    const errorMsg = document.getElementById('error-msg');
    errorMsg.innerText = msg;
    errorMsg.classList.remove('hidden');
}

function resetBtn() {
    const startBtn = document.getElementById('start-btn');
    startBtn.disabled = false;
    startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    startBtn.innerHTML = 'התחל תמלול';
}

// ===== PREVIEW FUNCTIONALITY =====

function showPreview() {
    if (!currentTaskId) return;

    fetch(`/preview/${currentTaskId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('שגיאה: ' + data.error);
                return;
            }

            document.getElementById('preview-text').textContent = data.text;
            document.getElementById('preview-modal').classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error loading preview:', error);
            alert('שגיאה בטעינת התצוגה המקדימה');
        });
}

function closePreview() {
    document.getElementById('preview-modal').classList.add('hidden');
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('preview-modal');
    if (e.target === modal) {
        closePreview();
    }
});

// ===== HISTORY FUNCTIONALITY =====

function loadHistory() {
    fetch('/history')
        .then(response => response.json())
        .then(data => {
            displayHistory(data.tasks || []);
        })
        .catch(error => console.error('Error loading history:', error));
}

function displayHistory(tasks) {
    const historyList = document.getElementById('history-list');

    if (!tasks || tasks.length === 0) {
        historyList.innerHTML = '<div class="text-gray-400 text-center py-4">אין היסטוריה עדיין</div>';
        return;
    }

    // Filter only completed tasks
    const completedTasks = tasks.filter(t => t.status === 'completed' && t.filename);

    if (completedTasks.length === 0) {
        historyList.innerHTML = '<div class="text-gray-400 text-center py-4">אין תמלולים שהושלמו</div>';
        return;
    }

    historyList.innerHTML = '';

    completedTasks.forEach(task => {
        const filename = task.filename ? task.filename.split(/[/\\]/).pop() : 'קובץ לא ידוע';
        const date = new Date(task.created_at * 1000).toLocaleString('he-IL');

        const item = document.createElement('div');
        item.className = 'flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition';

        item.innerHTML = `
            <div class="flex-1">
                <div class="font-medium text-gray-900 text-sm truncate">${filename}</div>
                <div class="text-xs text-gray-500">${date}</div>
            </div>
            <a href="/download/${task.task_id}" 
               class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm transition">
                הורד
            </a>
        `;

        historyList.appendChild(item);
    });
}

function toggleHistory() {
    const historyPanel = document.getElementById('history-panel');
    const toggleBtn = document.getElementById('history-toggle-btn');

    if (historyPanel.classList.contains('hidden')) {
        historyPanel.classList.remove('hidden');
        toggleBtn.innerHTML = `
            <span>📋 היסטוריית תמלולים</span>
            <span>הסתר היסטוריה ▲</span>
        `;
        loadHistory(); // Refresh when opening
    } else {
        historyPanel.classList.add('hidden');
        toggleBtn.innerHTML = `
            <span>📋 היסטוריית תמלולים</span>
            <span>הצג היסטוריה ▼</span>
        `;
    }
}
