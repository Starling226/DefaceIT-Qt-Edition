# Use Python 3.11 as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libglx0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download YOLO model with retry logic and SSL handling
RUN for i in 1 2 3 4 5; do \
        curl -L --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 300 \
        -o yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt && break || \
        (echo "Download attempt $i failed, retrying..." && sleep 10); \
    done && \
    if [ ! -f yolo11n.pt ]; then \
        echo "Failed to download YOLO model after 5 attempts" && exit 1; \
    fi

# Copy application files
COPY web_app.py .
COPY video_blur_core.py .
COPY languages.py .
COPY templates/ templates/

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Expose port
EXPOSE 8080

# Set the entrypoint
CMD ["python", "web_app.py"]
