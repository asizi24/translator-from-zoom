// Popup script for Audio Study Assistant Extension

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const apiUrlInput = document.getElementById('apiUrl');
const autoUploadToggle = document.getElementById('autoUpload');
const saveBtn = document.getElementById('saveBtn');
const status = document.getElementById('status');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');

// Load saved config
chrome.runtime.sendMessage({ action: 'getConfig' }, (response) => {
    if (response) {
        apiUrlInput.value = response.API_BASE_URL || '';
        autoUploadToggle.checked = response.AUTO_UPLOAD_ENABLED !== false;
    }
});

// Save settings
saveBtn.addEventListener('click', () => {
    const config = {
        API_BASE_URL: apiUrlInput.value.trim(),
        AUTO_UPLOAD_ENABLED: autoUploadToggle.checked
    };

    chrome.runtime.sendMessage({ action: 'updateConfig', config }, (response) => {
        if (response && response.success) {
            showStatus('ההגדרות נשמרו בהצלחה!', 'success');
        }
    });
});

// Upload zone events
uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

async function handleFile(file) {
    if (!apiUrlInput.value.trim()) {
        showStatus('אנא הזן כתובת שרת תחילה', 'error');
        return;
    }

    showStatus('<span class="loading-spinner"></span> מעלה ומנתח...', 'loading');
    progressBar.classList.add('show');
    progressFill.style.width = '30%';

    try {
        // Read file as data URL
        const reader = new FileReader();
        reader.onload = async () => {
            progressFill.style.width = '50%';

            chrome.runtime.sendMessage({
                action: 'uploadFile',
                file: reader.result,
                filename: file.name
            }, (response) => {
                progressFill.style.width = '100%';

                if (response && response.success) {
                    showStatus('✅ הניתוח הושלם! נפתח טאב חדש...', 'success');
                } else {
                    showStatus(`❌ שגיאה: ${response?.error || 'Unknown error'}`, 'error');
                }

                setTimeout(() => {
                    progressBar.classList.remove('show');
                    progressFill.style.width = '0%';
                }, 2000);
            });
        };

        reader.readAsDataURL(file);

    } catch (error) {
        showStatus(`❌ שגיאה: ${error.message}`, 'error');
        progressBar.classList.remove('show');
    }
}

function showStatus(message, type) {
    status.innerHTML = message;
    status.className = `status show ${type}`;

    if (type !== 'loading') {
        setTimeout(() => {
            status.classList.remove('show');
        }, 5000);
    }
}
