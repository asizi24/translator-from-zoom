/**
 * Content Script for Audio Study Assistant
 * Runs on Zoom recording pages to detect and extract audio/video sources
 */

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getVideoSource') {
        const videoUrl = findVideoSource();
        sendResponse({ url: videoUrl });
    }
    return true; // Keep message channel open for async response
});

// Find video/audio source on the page
function findVideoSource() {
    // Try video element
    const video = document.querySelector('video');
    if (video && video.src) {
        console.log('Found video source:', video.src);
        return video.src;
    }

    // Try audio element
    const audio = document.querySelector('audio');
    if (audio && audio.src) {
        console.log('Found audio source:', audio.src);
        return audio.src;
    }

    // Try source elements inside video
    const videoSource = document.querySelector('video source');
    if (videoSource && videoSource.src) {
        console.log('Found video source element:', videoSource.src);
        return videoSource.src;
    }

    // Try source elements inside audio
    const audioSource = document.querySelector('audio source');
    if (audioSource && audioSource.src) {
        console.log('Found audio source element:', audioSource.src);
        return audioSource.src;
    }

    // Try to find media elements by class/id (Zoom-specific)
    const zoomVideo = document.querySelector('[class*="video"]') ||
        document.querySelector('[id*="video"]');
    if (zoomVideo && zoomVideo.src) {
        console.log('Found Zoom video element:', zoomVideo.src);
        return zoomVideo.src;
    }

    console.warn('No video or audio source found on page');
    return null;
}

// Auto-detect when video loads
const observer = new MutationObserver(() => {
    const video = document.querySelector('video');
    const audio = document.querySelector('audio');

    if (video || audio) {
        console.log('Media element detected on page');
        // Store detection state
        chrome.storage.local.set({
            mediaDetected: true,
            pageUrl: window.location.href
        });
    }
});

// Start observing
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Initial check
if (document.querySelector('video') || document.querySelector('audio')) {
    chrome.storage.local.set({
        mediaDetected: true,
        pageUrl: window.location.href
    });
}
