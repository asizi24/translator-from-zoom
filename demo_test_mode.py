"""
Quick Test Mode Demo
Demonstrates the test mode functionality in action
"""

import time
from transcriber_engine import TranscriptionManager

print("\n" + "="*60)
print("🧪 TEST MODE DEMONSTRATION")
print("="*60 + "\n")

# Initialize manager in test mode
print("1️⃣  Initializing TranscriptionManager in test mode...")
manager = TranscriptionManager(test_mode=True)
print("   ✅ Manager initialized\n")

# Submit a test task
print("2️⃣  Submitting test task...")
task_id = manager.submit_task(
    url="https://example.com/test_video.mp4",
    test_mode=True
)
print(f"   ✅ Task submitted: {task_id[:8]}...\n")

# Poll status
print("3️⃣  Polling task status...\n")
start_time = time.time()

while True:
    status = manager.get_status(task_id)
    
    current_status = status.get('status')
    progress = status.get('progress', 0)
    message = status.get('message', '')
    
    print(f"   [{progress:3}%] {current_status:12} │ {message}")
    
    if current_status == 'completed':
        elapsed = time.time() - start_time
        print(f"\n   ✅ Task completed in {elapsed:.2f} seconds!")
        print(f"   📄 Output file: {status.get('filename', 'N/A')}")
        
        # Verify file exists
        import os
        filename = status.get('filename')
        if filename and os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"   📊 File size: {file_size} bytes")
            
            # Show first few lines
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')[:5]
                print(f"\n   📝 First 5 lines of transcript:")
                for line in lines:
                    if line.strip():
                        print(f"      {line}")
        
        break
    
    elif current_status == 'error':
        print(f"\n   ❌ Task failed: {status.get('error', 'Unknown error')}")
        break
    
    time.sleep(0.3)

print("\n" + "="*60)
print("✅ TEST MODE DEMO COMPLETE")
print("="*60 + "\n")
