"""
Configuration module for Flask Transcription App.
Handles secure loading of environment variables and application settings.
"""
import os
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration class."""
    
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    ENV = os.getenv('FLASK_ENV', 'production')  # Default to production for safety
    DEBUG = ENV == 'development'
    
    # API Keys
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    HF_TOKEN = os.getenv('HF_TOKEN')
    
    # Application settings
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max upload
    UPLOAD_FOLDER = 'uploads'
    DOWNLOAD_FOLDER = 'downloads'
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
    
    # Janitor settings
    JANITOR_INTERVAL_HOURS = 1  # Run cleanup every hour
    JANITOR_FILE_MAX_AGE_HOURS = 24  # Delete files older than 24 hours
    
    # Logging settings
    LOG_FILE = 'app.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB per log file
    LOG_BACKUP_COUNT = 5  # Keep 5 backup log files
    
    @classmethod
    def validate(cls):
        """
        Validate critical configuration.
        Returns (success: bool, errors: list, warnings: list)
        """
        errors = []
        warnings = []
        
        # Check SECRET_KEY
        if not cls.SECRET_KEY:
            # Generate a temporary one but warn
            cls.SECRET_KEY = secrets.token_hex(32)
            warnings.append(
                "⚠️  FLASK_SECRET_KEY not set in .env - using temporary key. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        
        # Check API keys (warnings only, not critical)
        if not cls.GOOGLE_API_KEY:
            warnings.append(
                "⚠️  GOOGLE_API_KEY not set - AI features will be disabled. "
                "Get key at: https://aistudio.google.com/app/apikey"
            )
        
        if not cls.HF_TOKEN:
            warnings.append(
                "⚠️  HF_TOKEN not set - Speaker diarization will be disabled. "
                "Get token at: https://huggingface.co/settings/tokens"
            )
        
        # Check folders exist or can be created
        for folder in [cls.UPLOAD_FOLDER, cls.DOWNLOAD_FOLDER]:
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder, exist_ok=True)
                except Exception as e:
                    errors.append(f"❌ Cannot create {folder}/ folder: {e}")
        
        return len(errors) == 0, errors, warnings
    
    @classmethod
    def is_development(cls):
        """Check if running in development mode."""
        return cls.DEBUG
    
    @classmethod
    def is_production(cls):
        """Check if running in production mode."""
        return not cls.DEBUG


def get_config():
    """
    Get validated configuration.
    Raises SystemExit if critical errors found.
    """
    success, errors, warnings = Config.validate()
    
    # Print warnings
    if warnings:
        print("\n⚠️  CONFIGURATION WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
        print()
    
    # Handle errors
    if not success:
        print("\n❌ CONFIGURATION ERRORS:")
        for error in errors:
            print(f"  {error}")
        print("\n⚠️  Please fix these errors before running the application.\n")
        raise SystemExit(1)
    
    return Config


# Export for convenience
__all__ = ['Config', 'get_config']
