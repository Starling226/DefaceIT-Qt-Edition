#!/bin/bash

# DefaceIT Docker Compose Runner Script
# Alternative way to run using docker-compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        echo "Detected: Linux"
        if [ -z "$DISPLAY" ]; then
            echo "ERROR: DISPLAY environment variable is not set"
            exit 1
        fi
        xhost +local:docker 2>/dev/null || echo "Warning: Could not run xhost"
        ;;
    Darwin*)
        echo "Detected: macOS"
        if ! pgrep -x "Xquartz" > /dev/null; then
            echo "ERROR: XQuartz is not running"
            echo "Please install and start XQuartz:"
            echo "  1. Install: brew install --cask xquartz"
            echo "  2. Start XQuartz from Applications"
            echo "  3. Run: xhost +localhost"
            exit 1
        fi
        export DISPLAY=:0
        xhost +localhost 2>/dev/null || echo "Warning: Could not run xhost"
        ;;
    *)
        echo "ERROR: Unsupported OS: ${OS}"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  DefaceIT Docker Compose Setup"
echo "=========================================="
echo ""

# Create input/output directories
mkdir -p input output

# Build and run
echo "Building and starting DefaceIT..."
docker-compose up --build

echo ""
echo "DefaceIT stopped."

