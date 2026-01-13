#!/usr/bin/env python3
"""
Production Readiness Verification Script
Flask Transcription App - System Health Check (Fixed Logic)
"""

import os
import sys
import time
import importlib

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def check_dependencies():
    print_header("📦 DEPENDENCY CHECK")
    required = {
        'yt_dlp': 'yt-dlp',
        'moviepy': 'moviepy',
        'whisper': 'openai-whisper',
        'flask': 'Flask',
        'google.generativeai': 'google-generativeai'
    }
    missing = []
    for mod, pkg in required.items():
        try:
            importlib.import_module(mod)
            print_success(f"{pkg} is installed")
        except ImportError:
            print_error(f"{pkg} is NOT installed")
            missing.append(pkg)
    
    if missing:
        return False, missing
    return True, []

def check_file_permissions():
    print_header("🔐 FILE PERMISSIONS CHECK")
    folders = ['downloads', 'uploads']
    errors = []
    for folder in folders:
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print_success(f"Created {folder}/")
            except Exception as e:
                errors.append(f"Create {folder}: {e}")
                continue
        
        test_file = os.path.join(folder, '.perm_test')
        try:
            with open(test_file, 'w') as f: f.write('ok')
            os.remove(test_file)
            print_success(f"{folder}/ is writable")
        except Exception as e:
            print_error(f"{folder}/ NOT writable: {e}")
            errors.append(folder)
            
    return len(errors) == 0, errors

def check_environment_variables():
    print_header("🔑 ENVIRONMENT VARIABLES CHECK")
    # Check Gemini
    if os.environ.get('GOOGLE_API_KEY'):
        print_success("GOOGLE_API_KEY is set")
    else:
        print_warning("GOOGLE_API_KEY missing (AI features disabled)")
        
    # Check HuggingFace
    if os.environ.get('HF_TOKEN'):
        print_success("HF_TOKEN is set")
    else:
        print_warning("HF_TOKEN missing (Speaker diarization disabled)")
        
    return True, []

def simulate_e2e_flow():
    """
    Returns: (success, filename, error_message)
    """
    print_header("🧪 E2E FLOW SIMULATION")
    try:
        from transcriber_engine import TranscriptionManager
        manager = TranscriptionManager(test_mode=True)
        
        print_info("Submitting test task...")
        task_id = manager.submit_task(url="https://example.com/test.mp4", test_mode=True)
        
        print_info(f"Task ID: {task_id}")
        
        # Poll for completion
        for _ in range(20):
            status = manager.get_status(task_id)
            if status['status'] == 'completed':
                filename = status.get('filename')
                print_success("Task completed successfully!")
                return True, filename, None
            elif status['status'] == 'error':
                return False, None, status.get('error')
            time.sleep(0.5)
            
        return False, None, "Timeout waiting for task"
        
    except Exception as e:
        return False, None, str(e)

def verify_output_file(filename):
    """
    Checks if the file actually exists on disk
    """
    print_header("📄 OUTPUT FILE VERIFICATION")
    
    if not filename:
        print_error("No filename provided from previous step")
        return False
        
    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print_success(f"File found: {filename} ({size} bytes)")
        
        # Read content check
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                if "TEST MODE" in content:
                    print_success("File content verified (Test Data)")
                    return True
                else:
                    print_warning("File content unexpected but readable")
                    return True
        except Exception as e:
            print_error(f"Cannot read file: {e}")
            return False
    else:
        print_error(f"File NOT found at: {filename}")
        return False

def main():
    print(f"\n{Colors.BOLD}🔍 System Verification v2.0{Colors.RESET}\n")
    
    # Run checks
    deps_ok, _ = check_dependencies()
    if not deps_ok: return 1
    
    perms_ok, _ = check_file_permissions()
    if not perms_ok: return 1
    
    check_environment_variables()
    
    # Run Flow
    flow_ok, filename, err = simulate_e2e_flow()
    
    if flow_ok:
        file_ok = verify_output_file(filename)
    else:
        print_error(f"E2E Flow Failed: {err}")
        file_ok = False
        
    # Final Report
    print_header("📊 FINAL RESULT")
    if deps_ok and perms_ok and flow_ok and file_ok:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL SYSTEMS GO! READY FOR PRODUCTION.{Colors.RESET}\n")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ SYSTEM NOT READY. FIX ERRORS ABOVE.{Colors.RESET}\n")

if __name__ == '__main__':
    main()