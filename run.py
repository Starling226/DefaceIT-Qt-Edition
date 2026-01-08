#!/usr/bin/env python3

import sys
import os
import platform
import subprocess
from pathlib import Path

def check_python():
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)

def check_pyqt5():
    """Check if PyQt5 can be imported."""
    try:
        import PyQt5.QtWidgets  # QtWidgets is the most reliable module to test
        return True
    except ImportError:
        return False


def find_venv_python():
    app_dir = Path(__file__).parent
    system = platform.system()
    
    if system == "Windows":
        venv_python = app_dir / "venv" / "Script" / "python.exe"
    else:
        venv_python = app_dir / "venv" / "bin" / "python3"
    
    venv_python = Path(venv_python)
    if venv_python.exists():
        return str(venv_python)
    return None

def run_app():
    app_dir = Path(__file__).parent
    os.chdir(app_dir)
    
    system = platform.system()
    venv_python = find_venv_python()
    
    if venv_python:
        print("Using virtual environment...")
        python_cmd = venv_python
    else:
        print("Using system Python...")
        python_cmd = sys.executable
    
    system = platform.system()

    if not check_pyqt5():
        print("\nWARNING: PyQt5 not found!")
        print("Attempting to use system Python which might have PyQt5 installed...")

        # Try system Python path (common on macOS/Linux)
        if system == "Darwin":  # macOS
            system_python = "/usr/bin/python3"
            if os.path.exists(system_python):
                python_cmd = system_python
                print(f"Using system Python: {python_cmd}")
                # You could exec() or os.system() here if you want to rerun with system Python
                # But usually pip install will fix it in venv, so we guide instead
            else:
                print("\nERROR: PyQt5 is required but not found.")
                print("Please install it:")
                print("  macOS:   brew install qt@5")
                print("           then pip install pyqt5")
                print("  (or run setup.sh which handles this)")
                sys.exit(1)

        elif system == "Linux":
            print("\nERROR: PyQt5 is required but not found.")
            print("Please install it:")
            print("  Ubuntu/Debian: sudo apt update && sudo apt install python3-pyqt5")
            print("  Fedora/Rocky/Alma: sudo dnf install python3-pyqt5")
            print("  Arch: sudo pacman -S python-pyqt5")
            print("After install, run: pip install pyqt5 (in your virtual environment)")
            sys.exit(1)

        else:
            print("\nERROR: PyQt5 is required but not found.")
            print("Please install PyQt5 manually:")
            print("  pip install pyqt5")
            print("Or install system packages if available on your OS.")
            sys.exit(1)

    # If we reach here, PyQt5 is available
    print("✓ PyQt5 found - starting application...")


    gui_file = app_dir / "defaceit_gui.py"
    
    if not gui_file.exists():
        print(f"ERROR: {gui_file} not found!")
        sys.exit(1)
    
    print(f"\nStarting DefaceIT...")
    print(f"Python: {python_cmd}")
    print(f"GUI: {gui_file}\n")
    
    try:
        if system == "Windows":
            subprocess.run([python_cmd, str(gui_file)], check=True)
        else:
            os.execv(python_cmd, [python_cmd, str(gui_file)])
    except KeyboardInterrupt:
        print("\n\nApplication closed by user.")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Failed to start application: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_python()
    run_app()
