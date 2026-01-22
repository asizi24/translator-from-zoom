import os
import sys
import importlib
import requests
import time
from dotenv import load_dotenv

# Load env variables locally
load_dotenv()

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
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}[ERR] {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")

def check_dependencies():
    print_header("[ DEPENDENCY CHECK ]")
    required = {
        'fastapi': 'FastAPI',
        'google.cloud.storage': 'google-cloud-storage',
        'vertexai': 'google-cloud-aiplatform',
        'uvicorn': 'uvicorn',
        'yt_dlp': 'yt-dlp'
    }
    missing = []
    for mod, pkg in required.items():
        try:
            importlib.import_module(mod)
            print_success(f"{pkg} is installed")
        except ImportError:
            print_error(f"{pkg} is NOT installed")
            missing.append(pkg)
    return len(missing) == 0

def check_env_vars():
    print_header("[ ENV VARS CHECK ]")
    vars = ['PROJECT_ID', 'BUCKET_NAME', 'GOOGLE_APPLICATION_CREDENTIALS']
    missing = []
    for v in vars:
        val = os.getenv(v)
        if val:
            print_success(f"{v} is set: {val}")
        else:
            print_error(f"{v} is MISSING")
            missing.append(v)
    return len(missing) == 0

def check_service_health():
    print_header("[ SERVICE HEALTH CHECK ]")
    try:
        # Assuming running inside container or locally on port 8000
        url = "http://localhost:8000/"
        print(f"Pinging {url}...")
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            print_success("Service is responding (HTTP 200)")
            return True
        else:
            print_error(f"Service returned {res.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect: {e}")
        return False

def check_model_access():
    print_header("[ MODEL ACCESS CHECK ]")
    # This is the critical check consistent with previous failures
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        project_id = os.getenv("PROJECT_ID")
        location = os.getenv("LOCATION", "us-central1")
        
        if not project_id:
            print_error("Cannot check model: PROJECT_ID missing")
            return False

        print(f"Initializing Vertex AI ({project_id})...")
        vertexai.init(project=project_id, location=location)
        
        model_name = "gemini-2.0-flash"
        print(f"Testing model: {model_name}...")
        model = GenerativeModel(model_name)
        # Dry run generation
        res = model.generate_content("Hello", stream=False)
        print_success("Model generation successful!")
        return True
        
    except Exception as e:
        print_error(f"Model verification FAILED: {e}")
        return False

def main():
    print(f"\n{Colors.BOLD}*** FastAPI System Verification ***{Colors.RESET}\n")
    
    if not check_dependencies():
        print_error("Dependency check failed")
        
    if not check_env_vars():
        print_error("Environment check failed")
        
    # Optional: check if service is running (might fail if run inside container without server)
    # check_service_health() 
    
    if not check_model_access():
        print_error("Critical AI Model check failed")
        sys.exit(1)
        
    print(f"\n{Colors.GREEN}{Colors.BOLD}*** SYSTEM READY ***{Colors.RESET}\n")

if __name__ == "__main__":
    main()
