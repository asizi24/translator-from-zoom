@echo off
echo ============================================
echo   Zoom Transcriber - Windows Installation
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv .venv

echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies (this may take a few minutes)...
pip install --upgrade pip
pip install -r requirements.txt

echo [4/4] Installation complete!
echo.
echo ============================================
echo   Installation Successful!
echo ============================================
echo.
echo To start the app, run:
echo   python run_local.py
echo.
echo Or double-click: start.bat
echo.

REM Create start.bat for easy launching
echo @echo off > start.bat
echo call .venv\Scripts\activate.bat >> start.bat
echo python run_local.py >> start.bat

echo Created start.bat for easy launching!
pause
