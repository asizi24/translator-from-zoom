import requests
import time
import sys

BASE_URL = "https://zoom-translator-3bnlbakjyq-uc.a.run.app"

def log(msg, type="INFO"):
    print(f"[{type}] {msg}")

def test_root():
    log(f"Testing Connectivity to {BASE_URL}...")
    try:
        resp = requests.get(BASE_URL)
        if resp.status_code == 200:
            log("Root endpoint returned 200 OK", "SUCCESS")
            return True
        else:
            log(f"Root endpoint failed: {resp.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"Connectivity check failed: {e}", "ERROR")
        return False

def test_async_flow():
    log("Testing Async Task Flow via /create_direct...")
    
    # 1. Create Task
    try:
        payload = {"text": "This is a test text for verification."}
        resp = requests.post(f"{BASE_URL}/create_direct", json=payload)
        
        if resp.status_code != 200:
            log(f"Create Direct failed: {resp.status_code} - {resp.text}", "ERROR")
            return False
            
        data = resp.json()
        task_id = data.get("task_id")
        if not task_id:
            log("No task_id returned", "ERROR")
            return False
            
        log(f"Task created: {task_id}", "SUCCESS")
        
        # 2. Poll Status
        for i in range(10):
            time.sleep(1)
            status_resp = requests.get(f"{BASE_URL}/status/{task_id}")
            if status_resp.status_code != 200:
                log(f"Status check failed: {status_resp.status_code}", "ERROR")
                continue
                
            status_data = status_resp.json()
            status = status_data.get("status")
            log(f"Polling status: {status} ({status_data.get('progress')}%)")
            
            if status == "completed":
                log("Task completed successfully", "SUCCESS")
                
                # 3. Verify Result
                dl_resp = requests.get(f"{BASE_URL}/download/{task_id}")
                if dl_resp.status_code == 200:
                   result_text = dl_resp.json().get("text", "")
                   if result_text == payload["text"]:
                       log("Download content verified match", "SUCCESS")
                       return True
                   else:
                       log(f"Content mismatch: {result_text}", "ERROR")
                       return False
                else:
                    log(f"Download failed: {dl_resp.status_code}", "ERROR")
                    return False
                    
            if status == "error":
                log(f"Task failed with error: {status_data.get('error')}", "ERROR")
                return False
                
        log("Timed out waiting for task completion", "ERROR")
        return False
        
    except Exception as e:
        log(f"Async flow exception: {e}", "ERROR")
        return False

if __name__ == "__main__":
    print("------------------------------------------------")
    print("   Cloud Run Deployment Verification")
    print("------------------------------------------------")
    
    if not test_root():
        sys.exit(1)
        
    if not test_async_flow():
        sys.exit(1)
        
    print("\n[VERIFIED] System is operational.")
