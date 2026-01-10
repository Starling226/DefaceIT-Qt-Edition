@echo off
echo ==========================================
echo   DefaceIT - Setup Script
echo   For Windows
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher first
    echo Visit: https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found
echo.

echo Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment activated
echo.

echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo pip upgraded
echo.

echo Installing dependencies...
echo This may take a few minutes...
pip install -r requirements.txt
echo installing torch family from the CUDA 13.0 wheel index
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
echo.

if errorlevel 1 (
    echo ERROR: Installation failed
    echo Please check the error messages above
    pause
    exit /b 1
)

echo ==========================================
echo   Setup Complete!
echo ==========================================
echo.
echo Starting DefaceIT...
echo.
python run_qt.py
pause
