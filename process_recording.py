import os
import sys
import subprocess
try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp library not found. Please install it using: pip install yt-dlp")
    sys.exit(1)

try:
    import whisper
except ImportError:
    print("Error: openai-whisper library not found. Please install it using: pip install openai-whisper")
    sys.exit(1)

from moviepy import VideoFileClip

def download_zoom_recording(url):
    print(f"--- Step 1: Downloading Video from URL ---")
    output_template = '%(title)s.%(ext)s'
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'quiet': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            print(f"Download Success: {filename}")
            return filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

def process_recording(video_path):
    # Check if file exists
    if not os.path.exists(video_path):
        print(f"Error: File {video_path} not found.")
        return

    base_name = os.path.splitext(video_path)[0]
    audio_output = f"{base_name}.mp3"
    text_output = f"{base_name}.txt"

    print(f"\n--- Step 2: Converting Video to Audio ---")
    try:
        # Load video and extract audio
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_output)
        video.close()
        print("✓ Video -> MP3: Success")
    except Exception as e:
        print(f"Error converting video: {e}")
        return

    print(f"\n--- Step 3: Transcribing with OpenAI Whisper (Hebrew) ---")
    try:
        # Load whisper model
        print("Loading Whisper model...")
        model = whisper.load_model("base")  # You can use: tiny, base, small, medium, large
        
        # Transcribe audio with Hebrew language
        print(f"Transcribing {audio_output}...")
        result = model.transcribe(audio_output, language='he')
        
        # Save transcription to text file
        with open(text_output, "w", encoding="utf-8") as f:
            f.write(result["text"])
        
        print(f"✓ MP3 -> TXT: Success")
        print(f"✓ Transcript saved to: {text_output}")

    except Exception as e:
        print(f"Error transcribing audio: {e}")

# --- Execution ---
if __name__ == "__main__":
    target_file = None
    zoom_url = None

    # Check command line arguments
    if len(sys.argv) > 1:
        input_arg = sys.argv[1]
        
        # Check if input is a URL
        if input_arg.startswith("http"):
            zoom_url = input_arg
        elif os.path.exists(input_arg):
            target_file = input_arg
            print(f"Processing specified file: {target_file}")
        else:
            print(f"Warning: Specified file '{input_arg}' not found.")
    else:
        # Interactive mode: ask for URL
        print("=" * 60)
        print("Zoom Recording to Transcript (Hebrew)")
        print("=" * 60)
        zoom_url = input("\nEnter Zoom recording URL (or press Enter to skip): ").strip()
        
        if not zoom_url:
            # Fallback to auto-detection if no URL provided
            files = [f for f in os.listdir('.') if f.endswith('.mp4')]
            if files:
                target_file = files[0]
                print(f"\nAuto-detected video file: {target_file}")
                if len(files) > 1:
                    print(f"Note: Found {len(files)} MP4 files. Using: {target_file}")
            else:
                print("No .mp4 files found in directory and no URL provided.")
                sys.exit(0)

    # Download from URL if provided
    if zoom_url:
        print(f"\nDetected URL: {zoom_url}")
        downloaded_file = download_zoom_recording(zoom_url)
        if downloaded_file:
            target_file = downloaded_file
        else:
            print("Failed to download video. Exiting.")
            sys.exit(1)

    # Process the video file
    if target_file:
        print(f"\n{'=' * 60}")
        print(f"Processing: {target_file}")
        print(f"{'=' * 60}")
        process_recording(target_file)
        print(f"\n{'=' * 60}")
        print("✓ All steps completed successfully!")
        print(f"{'=' * 60}")
