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
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🎮 GPU Detected: {gpu_name}")
            print("⚡ Running in GPU mode (12x faster!)")
            os.environ['USE_GPU'] = 'true'
        else:
            print("💻 No NVIDIA GPU found, using CPU")
            cpu_count = os.cpu_count() or 4
            print(f"🔧 Using all {cpu_count} CPU cores")
            os.environ['CPU_THREADS'] = str(cpu_count)
    except ImportError:
        print("💻 Running in CPU-only mode")
        cpu_count = os.cpu_count() or 4
        os.environ['CPU_THREADS'] = str(cpu_count)

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
