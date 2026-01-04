# DefaceIT Docker Quick Start

This Docker setup allows you to run DefaceIT in a container while the GUI opens on your host OS.

## Prerequisites

1. **Docker** installed and running
2. **X11 forwarding** set up:
   - **Linux**: Usually works out of the box with X11
   - **macOS**: Install XQuartz (`brew install --cask xquartz`) and start it

## Quick Start

### Option 1: Using the run script (Recommended)

```bash
cd docker-version
./run-docker.sh
```

### Option 2: Using docker-compose

```bash
cd docker-version
./run-docker-compose.sh
```

### Option 3: Manual Docker commands

```bash
cd docker-version

# Build the image
docker build -t defaceit:latest .

# Run the container
docker run --rm -it \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$(pwd)/input:/app/input" \
    -v "$(pwd)/output:/app/output" \
    -v "$HOME/.Xauthority:/root/.Xauthority:rw" \
    --network host \
    defaceit:latest
```

## macOS Setup

If you're on macOS, you need XQuartz:

1. Install XQuartz:
   ```bash
   brew install --cask xquartz
   ```

2. Start XQuartz from Applications

3. Allow X11 connections:
   ```bash
   xhost +localhost
   ```

4. Set DISPLAY:
   ```bash
   export DISPLAY=:0
   ```

5. Run the Docker container

## File Access

- Place input videos in the `input/` directory
- Output videos will be saved to the `output/` directory
- Both directories are mounted as volumes, so files are accessible from your host OS

## Troubleshooting

- **GUI doesn't open**: Check that X11/XQuartz is running and `xhost` permissions are set
- **Permission errors**: Make sure Docker has access to X11 socket
- **File not found**: Ensure input files are in the `input/` directory or use absolute paths

