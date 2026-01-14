import unittest
import json
import time
from unittest.mock import patch, MagicMock
from app import app
import os

class TestAITutorSystem(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('transcriber_engine.yt_dlp.YoutubeDL')
    @patch('transcriber_engine.VideoFileClip')
    @patch('transcriber_engine.whisper.load_model')
    @patch('google.generativeai.GenerativeModel')
    def test_full_flow(self, mock_gemini, mock_whisper_load, mock_video_clip, mock_yt_dlp):
        # 1. Setup Mocks
        
        # Mock yt_dlp
        mock_ydl_instance = mock_yt_dlp.return_value.__enter__.return_value
        mock_ydl_instance.extract_info.return_value = {'title': 'test_video', 'ext': 'mp4'}
        mock_ydl_instance.prepare_filename.return_value = 'downloads/test_video.mp4'
        
        # Mock VideoFileClip
        mock_video_instance = mock_video_clip.return_value
        mock_video_instance.audio.write_audiofile.return_value = None
        
        # Mock Whisper
        mock_whisper_model = mock_whisper_load.return_value
        mock_whisper_model.transcribe.return_value = {"text": "This is a test transcript"}
        
        # Mock Gemini
        mock_gemini_instance = mock_gemini.return_value
        mock_response = MagicMock()
        mock_response.text = "This is a test answer from Gemini"
        mock_gemini_instance.generate_content.return_value = mock_response

        # Ensure directories exist for the test (normally app does this, but being safe)
        os.makedirs('downloads', exist_ok=True)
        os.makedirs('uploads', exist_ok=True)

        # 2. Hit /start
        print("\nStep 1: Starting transcription task...")
        response = self.app.post('/start', 
                               data=json.dumps({'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        task_id = data['task_id']
        self.assertIsNotNone(task_id)
        print(f"Task ID: {task_id}")

        # 3. Poll /status until complete
        print("Step 2: Polling status...")
        max_retries = 10
        completed = False
        for i in range(max_retries):
            response = self.app.get(f'/status/{task_id}')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            print(f"Status: {data['status']}, Progress: {data['progress']}%, Message: {data.get('message')}")
            
            if data['status'] == 'completed':
                completed = True
                break
            elif data['status'] == 'error':
                print(f"ERROR DETECTED: {data}")
                self.fail(f"Task failed with error: {data.get('error')}")
            
            time.sleep(1) # Give worker thread time to process
            
        self.assertTrue(completed, "Task did not complete in time")

        # 4. Hit /ask
        print("Step 3: Asking a question...")
        response = self.app.post('/ask',
                               data=json.dumps({
                                   'task_id': task_id,
                                   'question': 'What is this test about?'
                               }),
                               content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['answer'], "This is a test answer from Gemini")
        print(f"Gemini Answer: {data['answer']}")
        print("\nFull Flow Verified Successfully!")

if __name__ == '__main__':
    unittest.main()
