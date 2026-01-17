#!/usr/bin/env python3
"""
🚀 Zoom Transcriber - Local Launcher
Run this script to start the transcription app locally.
Opens your browser automatically!
"""

import os
import sys
import webbrowser
import time
import subprocess

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import faster_whisper
        print("✅ Dependencies OK")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def detect_hardware():
    """Detect GPU/CPU and set optimal configuration"""
    import platform
    cpu_count = os.cpu_count() or 4
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🎮 NVIDIA GPU Detected: {gpu_name}")
            print("⚡ Running in GPU mode (12x faster!)")
            os.environ['USE_GPU'] = 'true'
            return
    except ImportError:
        pass
    
    # CPU Mode - optimized for Intel
    print(f"💻 Running on CPU: {cpu_count} cores/threads")
    
    # Intel Ultra series have P-cores + E-cores
    # Use slightly fewer threads to avoid E-core bottleneck
    optimal_threads = max(cpu_count - 2, 4)  # Leave 2 threads for system
    os.environ['CPU_THREADS'] = str(optimal_threads)
    
    print(f"🔧 Using {optimal_threads} threads (optimized for Intel)")
    print("💡 Tip: Close other apps for faster transcription")

def main():
    print("=" * 50)
    print("🎙️  Zoom Transcriber - Local Mode")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Detect hardware
    detect_hardware()
    
    # Disable cloud features for local use
    os.environ['AUTO_SHUTDOWN'] = 'false'
    os.environ['FLASK_ENV'] = 'development'
    
    # Start server
    print("\n🚀 Starting server...")
    print("📍 Opening http://localhost:5000 in your browser...")
    
    # Open browser after short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open('http://localhost:5000')
    
    import threading
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.start()
    
    # Run Flask app
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

if __name__ == '__main__':
    main()
