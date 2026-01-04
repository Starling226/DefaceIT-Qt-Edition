FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgtk-3-0 \
    python3-tk \
    x11-apps \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY defaceit_gui.py .
COPY video_blur_core.py .
COPY languages.py .

# Create directories for input/output files
RUN mkdir -p /app/input /app/output

# Set environment variables
ENV DISPLAY=:0
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python3", "defaceit_gui.py"]

