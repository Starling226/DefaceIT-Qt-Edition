#!/bin/bash

# DefaceIT Docker Runner Script
# This script builds and runs the DefaceIT application in Docker
# The GUI will open on your host OS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        echo "Detected: Linux"
        # Check if X11 is available
        if [ -z "$DISPLAY" ]; then
            echo "ERROR: DISPLAY environment variable is not set"
            echo "Please make sure you're running this from an X11 session"
            exit 1
        fi
        
        # Allow X11 connections
        xhost +local:docker 2>/dev/null || echo "Warning: Could not run xhost (may need: sudo apt-get install x11-xserver-utils)"
        ;;
    Darwin*)
        echo "Detected: macOS"
        # Check if XQuartz is running
        if ! pgrep -x "Xquartz" > /dev/null; then
            echo "ERROR: XQuartz is not running"
            echo "Please install and start XQuartz:"
            echo "  1. Install: brew install --cask xquartz"
            echo "  2. Start XQuartz from Applications"
            echo "  3. Run: xhost +localhost"
            echo "  4. Then run this script again"
            exit 1
        fi
        
        # Set DISPLAY for macOS (XQuartz uses :0)
        if [ -z "$DISPLAY" ]; then
            export DISPLAY=:0
        fi
        
        # Allow X11 connections
        xhost +localhost 2>/dev/null || echo "Warning: Could not run xhost"
        
        # For macOS, we need to use the IP address instead of /tmp/.X11-unix
        # Get the IP address
        IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
        if [ -n "$IP" ]; then
            export DISPLAY=$IP:0
        fi
        ;;
    *)
        echo "ERROR: Unsupported OS: ${OS}"
        echo "This script supports Linux and macOS only"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  DefaceIT Docker Setup"
echo "=========================================="
echo ""

# Create input/output directories if they don't exist
mkdir -p input output

# Build the Docker image
echo "Building Docker image..."
docker build -t defaceit:latest .

if [ $? -ne 0 ]; then
    echo "ERROR: Docker build failed"
    exit 1
fi

echo ""
echo "Starting DefaceIT..."
echo "The GUI should open in a few seconds..."
echo ""

# Prepare Docker run command
DOCKER_CMD="docker run --rm -it \
    -e DISPLAY=$DISPLAY"

# Add X11 socket mount (Linux) or use network mode (macOS)
if [ "$OS" = "Linux" ]; then
    DOCKER_CMD="$DOCKER_CMD -v /tmp/.X11-unix:/tmp/.X11-unix:rw"
    if [ -f "$HOME/.Xauthority" ]; then
        DOCKER_CMD="$DOCKER_CMD -v $HOME/.Xauthority:/root/.Xauthority:rw"
    fi
    DOCKER_CMD="$DOCKER_CMD --network host"
else
    # macOS: use host network and IP-based DISPLAY
    DOCKER_CMD="$DOCKER_CMD --network host"
fi

# Add volume mounts
DOCKER_CMD="$DOCKER_CMD -v $(pwd)/input:/app/input \
    -v $(pwd)/output:/app/output \
    defaceit:latest"

# Run the container
eval $DOCKER_CMD

echo ""
echo "DefaceIT container stopped."

