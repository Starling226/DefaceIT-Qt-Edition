#!/bin/bash

echo "=========================================="
echo "  DefaceIT - Setup Script (PyQt5 Version)"
echo "  For Linux and macOS only"
echo "=========================================="
echo ""

# === 1. Check Python 3 ===
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not found."
    echo "Please install Python 3.8 or higher:"
    echo "  - Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  - Fedora/Rocky:  sudo dnf install python3 python3-pip"
    echo "  - macOS:         brew install python3"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# === 2. Check PyQt5 ===
echo "Checking for PyQt5..."
python3 -c "import PyQt5.QtWidgets" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  PyQt5 not found or not importable."
    echo "We will install it via pip in the virtual environment."
    echo "But first, ensure system dependencies are installed:"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS:   brew install qt@5 ffmpeg"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Ubuntu/Debian: sudo apt update && sudo apt install python3-pyqt5 ffmpeg libgl1-mesa-glx"
        echo "Fedora/Rocky:  sudo dnf install python3-pyqt5 qt5-qtbase ffmpeg mesa-libGL"
    fi
    echo ""
else
    echo "✓ PyQt5 is already available (system-wide)"
fi
echo ""

# === 3. Virtual Environment ===
echo "Creating/using virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# === 4. Activate venv ===
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# === 5. Upgrade pip ===
echo "Upgrading pip..."
pip install --upgrade pip --quiet
echo "✓ pip upgraded"
echo ""

# === 6. Install dependencies ===
echo "Installing Python dependencies from requirements.txt..."
echo "This may take a few minutes..."
pip install -r requirements.txt
# Then install torch family from the CUDA 13.0 wheel index
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "         Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Starting DefaceIT (PyQt5 GUI)..."
    echo ""
    python3 defaceit_gui.py
else
    echo ""
    echo "ERROR: Installation failed"
    echo "Please check the error messages above."
    echo ""
    echo "Common fixes:"
    echo "  - Run the system dependency install commands shown above"
    echo "  - Check internet connection"
    echo "  - Ensure enough disk space"
    echo "  - Try: pip install --no-cache-dir -r requirements.txt"
    exit 1
fi
