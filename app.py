from flask import Flask, render_template, request, jsonify, send_from_directory
from transcriber_engine import TranscriptionManager
from werkzeug.utils import secure_filename
from config import Config, get_config
import google.generativeai as genai
import os
import time
import json
import logging
from logging.handlers import RotatingFileHandler

# Initialize Flask app
app = Flask(__name__)

# Load and validate configuration
config = get_config()
app.config.from_object(config)
app.secret_key = config.SECRET_KEY

# Setup logging
def setup_logging():
    """Configure application logging with file rotation."""
    # Create logs directory if needed
    log_dir = os.path.dirname(config.LOG_FILE) if os.path.dirname(config.LOG_FILE) else '.'
    if log_dir != '.' and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add rotating file handler
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Add handler to root logger
    logging.getLogger().addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger(__name__)

# Ensure folders exist with proper permissions
def ensure_folders():
    """Create folders with explicit permissions for EC2 compatibility"""
    for folder in [config.UPLOAD_FOLDER, config.DOWNLOAD_FOLDER]:
        try:
            os.makedirs(folder, exist_ok=True)
            # On Linux, ensure writable by current user
            if os.name != 'nt':  # Not Windows
                os.chmod(folder, 0o755)
            logger.info(f"Folder ready: {folder}")
        except PermissionError as e:
            logger.error(f"Permission denied creating {folder}: {e}")
            logger.error("Fix with: sudo chown -R $USER:$USER .")
            raise

ensure_folders()

# Initialize TranscriptionManager with HF token for speaker diarization
logger.info("Initializing TranscriptionManager...")
manager = TranscriptionManager()

ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configure Google Gemini
if config.GOOGLE_API_KEY:
    genai.configure(api_key=config.GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("Google Gemini API configured")
else:
    gemini_model = None
    logger.warning("Google Gemini API not configured - AI features disabled")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """
    Health check endpoint for load balancers, monitoring, and uptime checks.
    Returns 200 OK if the server is running properly.
    """
    try:
        # Basic health indicators
        health_status = {
            "status": "healthy",
            "service": "Flask Transcription App",
            "timestamp": time.time(),
            "queue_size": manager.task_queue.qsize(),
            "total_tasks": len(manager.tasks),
            "api_configured": bool(os.getenv('GOOGLE_API_KEY'))
        }
        return jsonify(health_status), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

@app.route('/start', methods=['POST'])
def start():
    """Start a new transcription task and return task_id"""
    data = request.json
    url = data.get('url')
    # Allow test_mode for UI verification
    test_mode = data.get('test_mode', False)
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    task_id = manager.submit_task(url, test_mode=test_mode)
    return jsonify({
        "task_id": task_id,
        "status": "queued"
    })

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload and start transcription"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "error": f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # Secure the filename and save
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Submit task with file path
        task_id = manager.submit_task(file_path=filepath)
        
        return jsonify({
            "task_id": task_id,
            "status": "queued",
            "filename": filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status/<task_id>')
def status(task_id):
    """Get status of a specific task by task_id"""
    task_status = manager.get_status(task_id)
    
    if task_status is None:
        return jsonify({"error": "Task not found"}), 404
    
    return jsonify(task_status)

@app.route('/history')
def history():
    """Get all tasks (for history view)"""
    all_tasks = manager.get_all_tasks()
    
    # Convert to list sorted by creation time (newest first)
    tasks_list = []
    for task_id, task_data in all_tasks.items():
        tasks_list.append({
            'task_id': task_id,
            **task_data
        })
    
    tasks_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    
    return jsonify({
        "tasks": tasks_list,
        "count": len(tasks_list)
    })

@app.route('/preview/<task_id>')
def preview(task_id):
    """Get preview of transcribed text"""
    task_status = manager.get_status(task_id)
    
    if task_status is None:
        return jsonify({"error": "Task not found"}), 404
    
    if task_status['status'] != 'completed':
        return jsonify({"error": "Transcription not yet completed"}), 400
    
    transcript_text = task_status.get('transcript_text', '')
    
    if not transcript_text:
        # Fallback: try reading from file if text not in memory
        filename = task_status.get('filename')
        if filename and os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()
            except Exception as e:
                logger.error(f"Failed to read transcript file {filename}: {e}")
                return jsonify({"error": "Could not read transcript"}), 500
        else:
            return jsonify({"error": "Transcript not available"}), 404
    
    return jsonify({
        "task_id": task_id,
        "text": transcript_text,
        "filename": task_status.get('filename', '')
    })

@app.route('/download/<task_id>')
def download(task_id):
    """Download a file by task_id"""
    task_status = manager.get_status(task_id)
    
    if task_status is None:
        return jsonify({"error": "Task not found"}), 404
    
    if task_status['status'] != 'completed':
        return jsonify({"error": "Task not completed yet"}), 400
    
    filename = task_status.get('filename')
    if not filename:
        return jsonify({"error": "File not found"}), 404
    
    # Security: Ensure file is in allowed directories (prevent path traversal)
    abs_path = os.path.abspath(filename)
    allowed_dirs = [
        os.path.abspath(config.DOWNLOAD_FOLDER),
        os.path.abspath(config.UPLOAD_FOLDER)
    ]
    if not any(abs_path.startswith(d + os.sep) or abs_path == d for d in allowed_dirs):
        logger.warning(f"Attempted path traversal: {filename} -> {abs_path}")
        return jsonify({"error": "Access denied"}), 403
    
    if not os.path.exists(abs_path):
        return jsonify({"error": "File not found"}), 404
    
    # Extract directory and basename
    directory = os.path.dirname(abs_path)
    basename = os.path.basename(abs_path)
    
    return send_from_directory(directory, basename, as_attachment=True)

@app.route('/player/<task_id>')
def player(task_id):
    """Display the AI chat player for a completed transcription"""
    task_status = manager.get_status(task_id)
    
    if task_status is None:
        return "Task not found", 404
    
    if task_status['status'] != 'completed':
        return "Transcription not completed yet", 400
    
    return render_template('player.html', task_id=task_id)

@app.route('/export/<task_id>/<format>')
def export_document(task_id, format):
    """Export transcript as DOCX or PDF with RTL Hebrew support and speaker labels"""
    # Validate format
    if format not in ['docx', 'pdf']:
        return jsonify({"error": f"Unsupported format: {format}. Use 'docx' or 'pdf'."}), 400
    
    # Get task status
    task_status = manager.get_status(task_id)
    if not task_status:
        return jsonify({"error": "Task not found"}), 404
    
    if task_status['status'] != 'completed':
        return jsonify({"error": "Transcription not completed yet"}), 400
    
    # Get transcript segments (with speaker info)
    segments = task_status.get('transcript_segments', [])
    if not segments:
        # Fallback: try loading from JSON file
        filename = task_status.get('filename')
        if filename:
            segments_file = filename.replace('.txt', '_segments.json')
            if os.path.exists(segments_file):
                try:
                    with open(segments_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        segments = data.get('segments', [])
                except Exception as e:
                    logger.error(f"Could not load segments file: {e}")
                    return jsonify({"error": "Could not load transcript segments"}), 500
    
    if not segments:
        return jsonify({"error": "No transcript segments available for export"}), 404
    
    # Generate base filename
    base_filename = os.path.basename(task_status.get('filename', f'transcript_{task_id}'))
    base_filename = os.path.splitext(base_filename)[0]
    
    try:
        if format == 'docx':
            output_file = generate_docx_export(segments, base_filename, task_id)
        else:  # pdf
            output_file = generate_pdf_export(segments, base_filename, task_id)
        
        # Send file
        directory = os.path.dirname(output_file)
        filename = os.path.basename(output_file)
        
        logger.info(f"Exported {format.upper()} for task {task_id}: {output_file}")
        return send_from_directory(directory, filename, as_attachment=True)
    
    except Exception as e:
        logger.error(f"Export error ({format}): {e}", exc_info=True)
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


def generate_docx_export(segments, base_filename, task_id):
    """Generate DOCX file with RTL Hebrew support and speaker formatting"""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    
    doc = Document()
    
    # Add title
    title = doc.add_heading(f'תמלול: {base_filename}', level=1)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    
    # Group segments by speaker for better readability
    current_speaker = None
    paragraph = None
    
    for segment in segments:
        speaker = segment.get('speaker', 'UNKNOWN')
        text = segment.get('text', '').strip()
        
        if not text:
            continue
        
        # New speaker = new paragraph
        if speaker != current_speaker:
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
            
            # Add speaker label (bold)
            speaker_run = paragraph.add_run(f'{speaker}: ')
            speaker_run.bold = True
            speaker_run.font.size = Pt(12)
            speaker_run.font.color.rgb = RGBColor(0, 51, 102)  # Dark blue
            
            # Set RTL for the paragraph
            paragraph.paragraph_format.right_to_left = True
            
            # Add text
            text_run = paragraph.add_run(text)
            text_run.font.size = Pt(11)
            
            current_speaker = speaker
        else:
            # Same speaker, append to paragraph
            paragraph.add_run(' ' + text)
    
    # Save to downloads folder
    output_path = os.path.join(config.DOWNLOAD_FOLDER, f'{base_filename}.docx')
    doc.save(output_path)
    
    logger.info(f"Generated DOCX: {output_path}")
    return output_path


def generate_pdf_export(segments, base_filename, task_id):
    """Generate PDF file with RTL Hebrew support and speaker formatting"""
    from fpdf import FPDF
    
    class HebrewPDF(FPDF):
        def __init__(self):
            super().__init__()
            # Try to add Hebrew font, fallback to default
            try:
                self.add_font('Arial', '', r'C:\Windows\Fonts\arial.ttf', uni=True)
                self.add_font('Arial', 'B', r'C:\Windows\Fonts\arialbd.ttf', uni=True)
            except:
                # Fallback to built-in fonts if custom fonts fail
                pass
    
    pdf = HebrewPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Add title
    try:
        pdf.set_font('Arial', 'B', 16)
    except:
        pdf.set_font('Helvetica', 'B', 16)
    
    title_text = f'Transcript: {base_filename}'
    pdf.cell(0, 10, title_text, ln=True, align='C')
    pdf.ln(5)
    
    # Add segments grouped by speaker
    current_speaker = None
    
    try:
        pdf.set_font('Arial', '', 10)
    except:
        pdf.set_font('Helvetica', '', 10)
    
    for segment in segments:
        speaker = segment.get('speaker', 'UNKNOWN')
        text = segment.get('text', '').strip()
        
        if not text:
            continue
        
        # New speaker
        if speaker != current_speaker:
            pdf.ln(3)
            
            # Speaker label (bold) + text
            try:
                pdf.set_font('Arial', 'B', 11)
            except:
                pdf.set_font('Helvetica', 'B', 11)
            
            pdf.cell(0, 6, f'{speaker}: ', ln=False)
            
            try:
                pdf.set_font('Arial', '', 10)
            except:
                pdf.set_font('Helvetica', '', 10)
            
            # Use multi_cell for text wrapping
            pdf.multi_cell(0, 6, text)
            
            current_speaker = speaker
        else:
            # Same speaker, continue
            pdf.multi_cell(0, 6, text)
    
    # Save to downloads folder
    output_path = os.path.join(config.DOWNLOAD_FOLDER, f'{base_filename}.pdf')
    pdf.output(output_path)
    
    logger.info(f"Generated PDF: {output_path}")
    return output_path

@app.route('/ask', methods=['POST'])
def ask():
    """Handle AI questions about the transcript"""
    # Check if Gemini is configured
    if not gemini_model:
        return jsonify({
            "error": "Google Gemini API not configured. Please set GOOGLE_API_KEY environment variable.",
            "instructions": "Get your free API key at: https://aistudio.google.com/app/apikey"
        }), 500
    
    data = request.json
    task_id = data.get('task_id')
    question = data.get('question')
    
    if not task_id or not question:
        return jsonify({"error": "Missing task_id or question"}), 400
    
    # Get the transcript
    task_status = manager.get_status(task_id)
    if not task_status:
        return jsonify({"error": "Task not found"}), 404
    
    if task_status['status'] != 'completed':
        return jsonify({"error": "Transcription not completed yet"}), 400
    
    # Get transcript text
    transcript_text = task_status.get('transcript_text', '')
    
    if not transcript_text:
        # Fallback: read from file
        filename = task_status.get('filename')
        if filename and os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()
            except Exception as e:
                return jsonify({"error": f"Could not read transcript: {str(e)}"}), 500
        else:
            return jsonify({"error": "Transcript not available"}), 404
    
    # Construct prompt for Gemini
    system_prompt = """אתה מורה פרטי ידידותי ומומחה. התלמיד שלך לומד משיעור.
ענה על השאלה שלו בהתבסס **רק** על התמלול של השיעור שמצורף למטה.

כללים חשובים:
- תן תשובות תמציתיות ומעודדות
- אם נשאלת על קוד, חלץ אותו מהתמלול ותקן שגיאות דיבור/תמלול
- השתמש בעברית להסברים, אלא אם מבוקש קוד
- אם התשובה לא נמצאת בשיעור, אמר בבירור: "לא מצאתי את זה בשיעור"
- אם נשאלת לסכם, תן 5-7 נקודות עיקריות
- אם נשאלת לחלץ קוד, הצג אותו בפורמט markdown עם ```

תמלול השיעור:
"""
    
    full_prompt = f"{system_prompt}\n\n{transcript_text}\n\nשאלת התלמיד: {question}"
    
    try:
        # Generate response from Gemini
        response = gemini_model.generate_content(full_prompt)
        answer = response.text
        
        return jsonify({
            "answer": answer,
            "error": None
        })
    
    except Exception as e:
        error_msg = str(e)
        return jsonify({
            "error": f"Gemini API error: {error_msg}",
            "answer": None
        }), 500

@app.route('/generate_study_material', methods=['POST'])
def generate_study_material():
    """Generate AI-powered study material: summary and quiz"""
    # Check if Gemini is configured
    if not gemini_model:
        return jsonify({
            "error": "Google Gemini API not configured. Please set GOOGLE_API_KEY environment variable.",
            "instructions": "Get your free API key at: https://aistudio.google.com/app/apikey"
        }), 500
    
    data = request.json
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({"error": "Missing task_id"}), 400
    
    # Get the transcript
    task_status = manager.get_status(task_id)
    if not task_status:
        return jsonify({"error": "Task not found"}), 404
    
    if task_status['status'] != 'completed':
        return jsonify({"error": "Transcription not completed yet"}), 400
    
    # Get transcript text
    transcript_text = task_status.get('transcript_text', '')
    
    if not transcript_text:
        # Fallback: read from file
        filename = task_status.get('filename')
        if filename and os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()
            except Exception as e:
                return jsonify({"error": f"Could not read transcript: {str(e)}"}), 500
        else:
            return jsonify({"error": "Transcript not available"}), 404
    
    # Construct prompt for Gemini
    prompt = f"""נתח את תמלול השיעור הבא. החזר אובייקט JSON תקין במבנה המדויק הבא:

{{
  "summary": "סיכום תמציתי בן 3 פסקאות של השיעור בעברית",
  "key_points": ["נקודה 1", "נקודה 2", "נקודה 3"],
  "quiz": [
    {{
      "question": "טקסט השאלה בעברית?",
      "options": ["אפשרות א", "אפשרות ב", "אפשרות ג", "אפשרות ד"],
      "correct_index": 0,
      "explanation": "למה זו התשובה הנכונה"
    }}
  ]
}}

חשוב:
- הסיכום צריך להיות 3 פסקאות קצרות
- key_points צריך להכיל בדיוק 3 נקודות עיקריות
- quiz צריך להכיל בדיוק 5 שאלות
- כל שאלה חייבת להכיל בדיוק 4 אפשרויות
- correct_index הוא מספר בין 0-3 (אינדקס האפשרות הנכונה)
- ודא שהתשובה היא JSON תקין בלבד, ללא markdown או טקסט נוסף

תמלול השיעור:
{transcript_text}"""
    
    try:
        # Generate response from Gemini
        logger.info(f"Generating study material for task {task_id}")
        response = gemini_model.generate_content(prompt)
        answer_text = response.text.strip()
        
        # Clean markdown code blocks if present
        if answer_text.startswith('```'):
            # Remove markdown code blocks
            answer_text = answer_text.split('```')[1]
            if answer_text.startswith('json'):
                answer_text = answer_text[4:]
            answer_text = answer_text.strip()
        
        # Parse JSON
        try:
            study_material = json.loads(answer_text)
            
            # Validate structure
            required_keys = ['summary', 'key_points', 'quiz']
            for key in required_keys:
                if key not in study_material:
                    raise ValueError(f"Missing required key: {key}")
            
            # Validate quiz structure
            if len(study_material['quiz']) != 5:
                logger.warning(f"Quiz has {len(study_material['quiz'])} questions, expected 5")
            
            for i, q in enumerate(study_material['quiz']):
                if 'question' not in q or 'options' not in q or 'correct_index' not in q:
                    raise ValueError(f"Invalid quiz question structure at index {i}")
                if len(q['options']) != 4:
                    raise ValueError(f"Quiz question {i} must have exactly 4 options")
            
            logger.info(f"Successfully generated study material for task {task_id}")
            return jsonify(study_material)
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}. Response was: {answer_text[:500]}")
            return jsonify({
                "error": f"Failed to parse AI response as JSON: {str(e)}",
                "raw_response": answer_text[:500]
            }), 500
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                "error": f"Invalid study material structure: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Gemini API error: {e}", exc_info=True)
        error_msg = str(e)
        return jsonify({
            "error": f"Gemini API error: {error_msg}"
        }), 500

def validate_environment():
    """Validate critical environment variables and folders on startup"""
    logger.info("Validating environment...")
    
    # Configuration validation already done by get_config()
    # Just log status
    logger.info(f"Environment: {config.ENV}")
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"Upload folder: {config.UPLOAD_FOLDER}")
    logger.info(f"Download folder: {config.DOWNLOAD_FOLDER}")
    logger.info(f"AI features: {'Enabled' if gemini_model else 'Disabled'}")
    logger.info(f"Speaker diarization: {'Enabled' if config.HF_TOKEN else 'Disabled'}")
    
    return True

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("🚀 Flask Transcription App - Starting...")
    logger.info("="*60)
    
    # Validate environment before starting
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        exit(1)
    
    logger.info("✅ All checks passed! Starting server...")
    logger.info(f"Server running on http://0.0.0.0:5000")
    logger.info(f"Debug mode: {config.DEBUG}")
    
    if config.is_production():
        logger.warning("Running in PRODUCTION mode. Consider using a WSGI server (Gunicorn/Waitress) for production.")
    
    # Debug mode controlled by FLASK_ENV environment variable
    app.run(debug=config.DEBUG, port=5000, host='0.0.0.0')
