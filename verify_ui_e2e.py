import requests
import time
import webbrowser
import os

print("🚀 Starting End-to-End Verification")

# 1. Submit Test Task
print("1️⃣  Submitting test task via API...")
try:
    response = requests.post('http://localhost:8000/start', json={
        'url': 'https://example.com/test_video.mp4',
        'test_mode': True
    })
    
    if response.status_code == 200:
        data = response.json()
        task_id = data['task_id']
        print(f"   ✅ Task created: {task_id}")
    else:
        print(f"   ❌ Error creating task: {response.text}")
        exit(1)
        
    # 2. Wait for completion (approx 4-5 seconds in test mode)
    print("2️⃣  Waiting for processing...")
    for i in range(10):
        time.sleep(1)
        status_resp = requests.get(f'http://localhost:8000/status/{task_id}')
        status = status_resp.json()
        print(f"   Status: {status.get('status')} - {status.get('progress')}% - {status.get('message')}")
        
        if status.get('status') == 'completed':
            print("   ✅ Task completed!")
            break
            
    # 3. Verify Response Data
    print("3️⃣  Verifying response data...")
    # Check for core fields
    required_fields = ['transcript_segments', 'summary', 'quiz']
    missing_fields = [field for field in required_fields if field not in status]
    
    if missing_fields:
        print(f"   ❌ Missing required JSON fields: {missing_fields}")
        print(f"   Full status keys: {status.keys()}")
        exit(1)
        
    segments = status.get('transcript_segments')
    if isinstance(segments, list) and len(segments) > 0:
        print(f"   ✅ Speaker Diarization found: {len(segments)} segments")
        sample = segments[0]
        print(f"   Sample: [{sample.get('timestamp')}] {sample.get('speaker')}: {sample.get('text')[:50]}...")
    else:
        print("   ❌ Transcript segments missing or empty!")
        exit(1)

    if status.get('summary'):
        print("   ✅ Summary generated")
    
    if status.get('quiz'):
        print(f"   ✅ Quiz generated ({len(status['quiz'])} questions)")

    # 4. Open Browser for UI Check
    print("4️⃣  Opening browser for UI verification...")
    # webbrowser.open(f'http://localhost:5000/player/{task_id}')
    # Instead of webbrowser.open which might be ignored in this environment, 
    # we'll print the URL for the browser subagent
    print(f"VERIFY_URL: http://localhost:8000/player/{task_id}")

except Exception as e:
    print(f"   ❌ Connection failed: {e}")
    print("   Make sure the server is running!")
